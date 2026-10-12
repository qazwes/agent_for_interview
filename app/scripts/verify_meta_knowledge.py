"""验证已构建的元数据知识库；仅查询 MySQL/Qdrant/ES 和调用 Embedding。

从 my-agent 目录运行：python -m app.scripts.verify_meta_knowledge
配置由 -c/--conf 指定，默认 conf/meta_config.yaml。失败时返回非零退出码。
"""

import argparse
import asyncio
from collections import Counter
from contextlib import AsyncExitStack
from pathlib import Path

import yaml


def expected_metadata(config):
    """从实际配置推导数量和关系，避免将当前表/字段数量写死。"""
    tables = {t["name"]: t for t in config.get("tables", [])}
    columns = {
        f"{t['name']}.{c['name']}": {**c, "table_id": t["name"]}
        for t in tables.values() for c in t["columns"]
    }
    metrics = {m["name"]: m for m in config.get("metrics", [])}
    links = {(c, m["name"]) for m in metrics.values() for c in m["relevant_columns"]}
    return tables, columns, metrics, links


def point_counts(items):
    # 构建服务为每个字段/指标的名字、描述、每个别名分别生成一个 point。
    return Counter({key: 2 + len(item["alias"]) for key, item in items.items()})


class Report:
    def __init__(self):
        self.failed = 0

    def check(self, name, passed, detail=""):
        self.failed += int(not passed)
        print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"：{detail}" if detail else ""))


async def check_meta(report, session, dw, config):
    from sqlalchemy import select, text

    from app.models.column_info import ColumnInfoMySQL
    from app.models.metric_info import MetricInfoMySQL
    from app.models.table_info import TableInfoMySQL

    tables, columns, metrics, links = expected_metadata(config)
    models = {"table_info": TableInfoMySQL, "column_info": ColumnInfoMySQL,
              "metric_info": MetricInfoMySQL}
    actual = {}
    for name, expected in (("table_info", tables), ("column_info", columns), ("metric_info", metrics)):
        # 使用带 JSON 字段类型的 SELECT，让 SQLAlchemy 解析 alias/examples 等数组。
        # 原始 text(SELECT *) 会返回 JSON 字符串，导致与 YAML/Qdrant 列表比较时误判。
        rows = (await session.execute(select(models[name].__table__))).mappings().all()
        actual[name] = {row["id"]: dict(row) for row in rows}
        report.check(f"Meta {name} ID 和数量", set(actual[name]) == set(expected),
                     f"实际 {len(rows)}，配置期望 {len(expected)}")
        compare_keys = {"table_info": ("name", "role", "description"),
                        "column_info": ("name", "role", "description", "alias", "table_id"),
                        "metric_info": ("name", "description", "alias", "relevant_columns")}[name]
        mismatches = [f"{key}.{field}"
                      for key, item in expected.items() for field in compare_keys
                      if key not in actual[name] or actual[name][key][field] != item[field]]
        report.check(f"Meta {name} 业务定义", not mismatches,
                     "不一致字段：" + ", ".join(mismatches[:5]) if mismatches else "")
    rows = (await session.execute(text("SELECT column_id, metric_id FROM column_metric"))).all()
    actual_links = {tuple(row) for row in rows}
    report.check("Meta 指标依赖关系", actual_links == links,
                 f"实际 {len(rows)}，配置期望 {len(links)}")
    real_types = {name: await dw.get_column_types(name) for name in tables}
    mismatches = [key for key, c in columns.items()
                  if key in actual["column_info"]
                  and actual["column_info"][key]["type"] != real_types[c["table_id"]].get(c["name"])]
    report.check("Meta 字段类型与 DW 一致", not mismatches, ", ".join(mismatches[:5]))
    return actual


async def check_vectors(report, client, repository, expected, meta_rows, embedding_size):
    name = repository.collection_name
    if not await client.collection_exists(name):
        report.check(f"Qdrant {name} 存在", False)
        return
    info = await client.get_collection(name)
    report.check(f"Qdrant {name} 向量维度", getattr(info.config.params.vectors, "size", None) == embedding_size,
                 f"期望 {embedding_size}")
    actual_counts = Counter()
    payload_mismatches = set()
    offset = None
    while True:
        points, offset = await client.scroll(
            collection_name=name, limit=256, offset=offset, with_payload=True, with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            key = payload.get("id")
            actual_counts[key] += 1
            if key not in meta_rows:
                payload_mismatches.add(f"未知对象 {key}")
            else:
                payload_mismatches.update(
                    f"{key}.{field}" for field in set(payload) | set(meta_rows[key])
                    if field not in payload or field not in meta_rows[key]
                    or payload[field] != meta_rows[key][field]
                )
        if offset is None:
            break
    wanted = point_counts(expected)
    report.check(f"Qdrant {name} 对象覆盖和 point 数量", actual_counts == wanted,
                 f"实际 {sum(actual_counts.values())}，配置期望 {sum(wanted.values())}")
    report.check(f"Qdrant {name} payload 与 Meta 一致", not payload_mismatches,
                 "不一致字段：" + ", ".join(sorted(payload_mismatches)[:5]) if payload_mismatches else "")


async def check_values(report, es, repo, dw, columns):
    name = repo.index_name
    if not await es.indices.exists(index=name):
        report.check("ES value_index 存在", False)
        return
    mappings = await es.indices.get_mapping(index=name)
    properties = mappings[name]["mappings"]["properties"]
    report.check("ES 中文取值分词配置", properties.get("value", {}).get("analyzer") == "ik_max_word")
    wanted = {}
    for key, column in columns.items():
        if column["sync"]:
            values = await dw.get_column_values(column["table_id"], column["name"], 100000)
            wanted[key] = len(values)
            if len(values) == 100000:
                report.check(f"ES {key} 值域未达到采样上限", False,
                             "构建脚本最多同步 100000 个不同取值，需要分页才能确认完整性")
    response = await es.search(index=name, size=0, aggs={
        "columns": {"terms": {"field": "column_id", "size": max(1000, len(columns) + 1)}}
    }, track_total_hits=True)
    counts = {b["key"]: b["doc_count"] for b in response["aggregations"]["columns"]["buckets"]}
    report.check("ES 同步字段覆盖和取值数量", counts == wanted,
                 f"实际 {response['hits']['total']['value']}，DW 期望 {sum(wanted.values())}")
    probes = (("北京", "dim_business_unit.city", "北京"),
              ("R5300 G5", "dim_product.product_model", "R5300 G5"),
              ("高风险", "fact_project_snapshot.risk_level", "高风险"))
    for phrase, column_id, value in probes:
        # 使用应用的默认分数阈值和候选数量，验证真正参与问数的检索行为。
        results = await repo.search(phrase)
        report.check(f"ES 取值检索「{phrase}」",
                     any(item.column_id == column_id and str(item.value) == value for item in results),
                     f"期望 {column_id}={value}")


async def check_recall(report, embedding, column_repo, metric_repo, dimension):
    # 当前销售经管 demo 的小型验收集；不代表任意自然语言的检索质量。
    probes = (
        ("销售额", column_repo, "fact_sales_monthly.revenue_amount"),
        ("产品型号", column_repo, "dim_product.product_model"),
        ("销售收入", metric_repo, "销售收入"),
        ("商业目标", metric_repo, "商业目标"),
        ("收入完成率", metric_repo, "收入完成率"),
        ("目前有多少高风险项目", metric_repo, "当前高风险项目数"),
    )
    for phrase, repo, expected_id in probes:
        vector = await embedding.aembed_query(phrase)
        report.check(f"Embedding「{phrase}」维度", len(vector) == dimension)
        results = await repo.search(vector)
        ids = list(dict.fromkeys(item.id for item in results))
        report.check(f"向量召回「{phrase}」", expected_id in ids,
                     f"期望 {expected_id}；召回 {', '.join(ids[:5]) or '空'}")


async def verify(config_path):
    # 延迟导入运行依赖，让配置数量计算可以离线测试。
    from app.clients.embedding_client_manager import embedding_client_manager
    from app.clients.es_client_manager import es_client_manager
    from app.clients.mysql_client_manager import (
        dw_mysql_client_manager,
        meta_mysql_client_manager,
    )
    from app.clients.qdrant_client_manager import qdrant_client_manager
    from app.conf.app_config import app_config
    from app.repositories.es.value_es_repository import ValueESRepository
    from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
    from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
    from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    _, columns, metrics, _ = expected_metadata(config)
    report = Report()
    async with AsyncExitStack() as stack:
        for manager in (meta_mysql_client_manager, dw_mysql_client_manager,
                        qdrant_client_manager, es_client_manager):
            manager.init()
            stack.push_async_callback(manager.close)
        embedding_client_manager.init()
        meta_session = await stack.enter_async_context(meta_mysql_client_manager.session_factory())
        dw_session = await stack.enter_async_context(dw_mysql_client_manager.session_factory())
        dw = DWMySQLRepository(dw_session)
        column_repo = ColumnQdrantRepository(qdrant_client_manager.client)
        metric_repo = MetricQdrantRepository(qdrant_client_manager.client)
        value_repo = ValueESRepository(es_client_manager.client)
        actual = await check_meta(report, meta_session, dw, config)
        for repo, items, rows in ((column_repo, columns, actual["column_info"]),
                                 (metric_repo, metrics, actual["metric_info"])):
            await check_vectors(report, qdrant_client_manager.client, repo, items, rows,
                                app_config.qdrant.embedding_size)
        await check_values(report, es_client_manager.client, value_repo, dw, columns)
        await check_recall(report, embedding_client_manager.client, column_repo, metric_repo,
                           app_config.qdrant.embedding_size)
    print(f"验证结束：{report.failed} 项失败。")
    return int(report.failed > 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-c", "--conf", type=Path, default=Path("conf/meta_config.yaml"))
    args = parser.parse_args()
    try:
        code = asyncio.run(verify(args.conf))
    except Exception as exc:
        # 不输出连接 URL、密码或 SDK 原始错误详情。
        print(f"[ERROR] 验证中断（{type(exc).__name__}）。检查配置、服务日志及初始化状态。")
        code = 1
    raise SystemExit(code)


if __name__ == "__main__":
    main()
