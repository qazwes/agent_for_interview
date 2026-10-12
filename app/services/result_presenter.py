"""从最终 SQL、元数据和真实结果整理展示信息，不增加模型调用。"""
import math
from functools import lru_cache
from numbers import Number
from pathlib import Path

import sqlglot
import yaml
from sqlglot import exp


@lru_cache
def warehouse_schema():
    config = yaml.safe_load((Path(__file__).parents[2] / "conf/meta_config.yaml").read_text(encoding="utf-8"))
    tables = {t["name"]: t for t in config["tables"]}
    columns = {c["name"]: c for t in tables.values() for c in t["columns"]}
    return tables, columns


def build_presentation(query, sql, rows, metric_infos=()):
    tables, schema = warehouse_schema()
    try:
        tree = sqlglot.parse_one(sql, read="mysql")
        actual_tables = sorted({t.name for t in tree.find_all(exp.Table) if t.name in tables})
        used_columns = {c.name for c in tree.find_all(exp.Column)}
        projections = {e.alias_or_name: e for e in tree.selects}
        conditions = list(dict.fromkeys(w.this.sql(dialect="mysql") for w in tree.find_all(exp.Where)))
    except (sqlglot.errors.ParseError, AttributeError):
        actual_tables, used_columns, projections, conditions = [], set(), {}, []
    fields, stats = [], []
    for key in dict.fromkeys(k for row in rows for k in row):
        projection = projections.get(key)
        sources = {c.name for c in projection.find_all(exp.Column)} if projection is not None else {key}
        metadata = schema.get(key) or next((schema[c] for c in sources if c in schema), {})
        values = [r.get(key) for r in rows if r.get(key) is not None]
        numeric = bool(values) and all(isinstance(v, Number) and not isinstance(v, bool) and math.isfinite(float(v)) for v in values)
        aggregation = projection is not None and any(projection.find_all(exp.AggFunc))
        identity = not aggregation and any(c.endswith("_id") or c in {"year", "target_year", "month", "quarter", "day"} for c in sources)
        divisions = list(projection.find_all(exp.Div)) if projection is not None else []
        wan = any(isinstance(d.expression, exp.Literal) and d.expression.is_number and float(d.expression.this) == 10000 for d in divisions)
        financial = any("amount" in c for c in sources) or any(w in key for w in ("收入", "金额", "目标", "销售额"))
        ratio = any(w in key.lower() for w in ("pct", "rate", "ratio", "%", "率", "占比", "同比", "环比")) or any(not isinstance(d.expression, exp.Literal) for d in divisions)
        percent = ratio and ("pct" in key or "%" in key or (projection is not None and any(isinstance(n, exp.Literal) and n.this in ("100", "100.0") for n in projection.walk())))
        unit = "%" if percent else "比例" if ratio else "万元" if wan else "元" if financial else "台套" if any("quantity" in c for c in sources) else ""
        label = key if not key.isascii() or (aggregation and any(c.endswith("_id") for c in sources)) else (metadata.get("alias") or [key])[0]
        non_additive = projection is not None and any(projection.find_all(exp.Avg, exp.Min, exp.Max))
        field = {"key": key, "label": label, "kind": "metric" if numeric and not identity else "dimension", "unit": unit,
                 "additive": numeric and not identity and not ratio and not non_additive}
        fields.append(field)
        if field["kind"] == "metric":
            nums = [float(v) for v in values]
            stats.append({"key": key, "label": label, "unit": unit, "count": len(nums), "average": sum(nums) / len(nums),
                          "max": max(nums), "min": min(nums), "total": sum(nums) if field["additive"] else None})
    dimensions = [f for f in fields if f["kind"] == "dimension"]
    metrics = [f for f in fields if f["kind"] == "metric"]
    chart_type = "pie" if "饼图" in query or "占比" in query else "line" if "折线" in query or "趋势" in query else "bar"
    chart = {"type": chart_type, "dimension": dimensions[0]["key"], "metrics": [f["key"] for f in metrics]} if dimensions and metrics and rows else None
    if chart and chart_type == "pie":
        chart["metrics"] = [metrics[0]["key"]]
    definitions = [m for m in metric_infos if any(c.rsplit(".", 1)[-1] in used_columns for c in m.get("relevant_columns", []))]
    suggestions = [
        f"保持以下问题的时间与筛选条件：{query}。请列出相关数据明细。",
        f"保持以下问题的时间与筛选条件：{query}。请比较返回结果中的最高值与最低值。",
        f"保持以下问题的时间与筛选条件：{query}。请按产品线进一步拆分数据；若指标没有产品线粒度，请说明无法拆分。",
    ]
    return {"query": query, "sql": sql, "tables": actual_tables, "conditions": conditions,
            "metric_definitions": definitions, "columns": fields, "statistics": stats,
            "row_count": len(rows), "result_scope": "本次 SQL 返回的数据范围（排名查询仅包含返回的排名记录）",
            "chart": chart, "suggestions": suggestions if rows else []}
