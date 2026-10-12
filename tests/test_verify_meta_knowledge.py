"""验证脚本自身的离线测试；不假装完成容器里的知识库验收。"""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.base import Base
from app.models.column_info import ColumnInfoMySQL
from app.models.column_metric import ColumnMetricMySQL
from app.models.metric_info import MetricInfoMySQL
from app.models.table_info import TableInfoMySQL
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.scripts.verify_meta_knowledge import (
    Report,
    check_meta,
    check_recall,
    check_vectors,
    expected_metadata,
    point_counts,
)


@pytest.fixture
def metadata_db():
    """真实 SQLAlchemy JSON 读写，复现 text() 返回字符串的边界。"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    config = {
        "tables": [{"name": "dim_demo", "role": "dim", "description": "演示维度",
                    "columns": [{"name": "id", "role": "primary_key", "description": "主键",
                                 "alias": ["编号"], "sync": False},
                                {"name": "amount", "role": "measure", "description": "金额",
                                 "alias": ["收入"], "sync": False}]}],
        "metrics": [{"name": "收入", "description": "演示口径", "alias": ["收入额"],
                     "relevant_columns": ["dim_demo.amount"]}],
    }
    tables, columns, metrics, links = expected_metadata(config)
    with Session(engine) as session:
        session.add_all(TableInfoMySQL(id=k, **{f: v[f] for f in ("name", "role", "description")})
                        for k, v in tables.items())
        session.flush()
        session.add_all(ColumnInfoMySQL(id=k, type="int", examples=[1],
                                       **{f: v[f] for f in ("name", "role", "description", "alias", "table_id")})
                        for k, v in columns.items())
        session.add_all(MetricInfoMySQL(id=k, **v) for k, v in metrics.items())
        session.flush()
        session.add_all(ColumnMetricMySQL(column_id=c, metric_id=m) for c, m in links)
        session.commit()
        async_session = SimpleNamespace(execute=AsyncMock(side_effect=session.execute))
        dw = SimpleNamespace(get_column_types=AsyncMock(return_value={"id": "int", "amount": "int"}))
        yield config, session, async_session, dw
    engine.dispose()


def test_json_content_checks_pass_using_typed_queries(metadata_db):
    config, session, async_session, dw = metadata_db
    assert isinstance(session.execute(text("SELECT alias FROM column_info LIMIT 1")).scalar(), str)
    report = Report()
    actual = asyncio.run(check_meta(report, async_session, dw, config))
    assert report.failed == 0
    assert actual["column_info"]["dim_demo.id"]["alias"] == ["编号"]
    assert actual["column_info"]["dim_demo.id"]["examples"] == [1]
    assert actual["metric_info"]["收入"]["relevant_columns"] == ["dim_demo.amount"]

    # 来自 Qdrant 的列表 payload 必须与同样内容的 Meta JSON 列一致。
    client = SimpleNamespace(
        collection_exists=AsyncMock(return_value=True),
        get_collection=AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(
            params=SimpleNamespace(vectors=SimpleNamespace(size=1024))))),
        scroll=AsyncMock(return_value=([
            SimpleNamespace(payload=actual["column_info"][key])
            for key, count in point_counts(expected_metadata(config)[1]).items() for _ in range(count)
        ], None)),
    )
    asyncio.run(check_vectors(report, client, SimpleNamespace(collection_name="demo"),
                              expected_metadata(config)[1], actual["column_info"], 1024))
    assert report.failed == 0


def test_actual_definition_changes_still_fail_with_field_details(metadata_db, capsys):
    config, session, async_session, dw = metadata_db
    session.get(ColumnInfoMySQL, "dim_demo.id").alias = ["错误别名"]
    session.get(MetricInfoMySQL, "收入").description = "错误口径"
    session.commit()
    report = Report()
    asyncio.run(check_meta(report, async_session, dw, config))
    assert report.failed == 2
    output = capsys.readouterr().out
    assert "dim_demo.id.alias" in output
    assert "收入.description" in output


def test_key_column_repository_returns_lists_and_filters_roles(metadata_db):
    _, _, async_session, _ = metadata_db
    repository = MetaMySQLRepository(async_session)
    columns = asyncio.run(repository.get_key_columns_by_table_id("dim_demo"))
    assert len(columns) == 1
    assert columns[0].id == "dim_demo.id"
    assert columns[0].examples == [1]
    assert columns[0].alias == ["编号"]
    assert asyncio.run(repository.get_key_columns_by_table_id("other_table")) == []


def test_expected_counts_and_dependencies_from_actual_config():
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "conf/meta_config.yaml").read_text(encoding="utf-8"))
    tables, columns, metrics, links = expected_metadata(config)
    assert len(tables) == 9
    assert len(metrics) == 13
    assert all(column_id in columns and metric_id in metrics for column_id, metric_id in links)
    assert sum(point_counts(columns).values()) == sum(2 + len(c["alias"]) for c in columns.values())
    assert point_counts({"x": {"alias": ["收入", "销售额"]}}) == {"x": 4}


def test_vector_check_reports_duplicates_and_outdated_payload():
    async def run(points):
        client = SimpleNamespace(
            collection_exists=AsyncMock(return_value=True),
            get_collection=AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(
                params=SimpleNamespace(vectors=SimpleNamespace(size=1024))))),
            scroll=AsyncMock(side_effect=[(points[:1], "next"), (points[1:], None)]),
        )
        report = Report()
        await check_vectors(report, client, SimpleNamespace(collection_name="demo"),
                            {"x": {"alias": []}}, {"x": {"id": "x", "description": "新口径"}}, 1024)
        return report.failed

    good = SimpleNamespace(payload={"id": "x", "description": "新口径"})
    stale = SimpleNamespace(payload={"id": "x", "description": "旧口径"})
    assert asyncio.run(run([good, good])) == 0
    assert asyncio.run(run([good, good, stale])) == 2


def test_missing_collection_fails_without_creating_it():
    client = SimpleNamespace(collection_exists=AsyncMock(return_value=False))
    report = Report()
    asyncio.run(check_vectors(report, client, SimpleNamespace(collection_name="absent"), {}, {}, 1024))
    assert report.failed == 1


def test_recall_checks_expected_ids_not_just_nonempty_results():
    async def run():
        # 模型能返回正确维度，但检索到错误的旧电商对象，也必须判定失败。
        embedding = SimpleNamespace(aembed_query=AsyncMock(return_value=[0.1] * 1024))
        repo = SimpleNamespace(search=AsyncMock(return_value=[SimpleNamespace(id="fact_order.order_amount")]))
        report = Report()
        await check_recall(report, embedding, repo, repo, 1024)
        assert report.failed == 6
        assert repo.search.await_count == 6
    asyncio.run(run())
