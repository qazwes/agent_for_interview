"""离线验证 SQL 产物的关系、业务口径、样例和元数据一致性。

SQLite 适配仅剥离 MySQL 的部署语句、注释和索引语法；不替代 MySQL 8 方言验收。
"""

import asyncio
import json
import re
import sqlite3
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from sqlalchemy import UniqueConstraint

from app.models.column_info import ColumnInfoMySQL
from app.models.column_metric import ColumnMetricMySQL
from app.models.metric_info import MetricInfoMySQL
from app.models.table_info import TableInfoMySQL
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository

ROOT = Path(__file__).resolve().parents[1]


def load_mysql_fixture(connection, path):
    source = path.read_text(encoding="utf-8")
    source = re.sub(r"^--.*$", "", source, flags=re.MULTILINE)
    for statement in source.split(";"):
        statement = statement.strip()
        if not statement or statement.upper().startswith(("SET ", "USE ", "GRANT ", "CREATE DATABASE ")):
            continue
        statement = re.sub(r"\s+COMMENT(?:=|\s+)'(?:''|[^'])*'", "", statement)
        statement = re.sub(r"\s+ENGINE=InnoDB", "", statement)
        statement = re.sub(r"UNIQUE KEY \w+\s*\(", "UNIQUE (", statement)
        connection.execute(statement)


@pytest.fixture
def db():
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    load_mysql_fixture(connection, ROOT / "docker/mysql/dw.sql")
    load_mysql_fixture(connection, ROOT / "docker/mysql/meta.sql")
    yield connection
    connection.close()


def queries():
    source = (ROOT / "database/reference_queries.sql").read_text(encoding="utf-8")
    return [statement.strip() for statement in source.split(";") if statement.strip()]


def run(db, number):
    return [dict(row) for row in db.execute(queries()[number-1])]


def test_reference_questions(db):
    results = {number: run(db, number) for number in range(1, 13)}
    assert len(results[1]) == 4
    assert sum(row["revenue_wan"] for row in results[2]) == pytest.approx(2647.5)
    assert len(results[3]) == 6
    assert len(results[4]) == 12
    beijing = next(row for row in results[4] if row["business_unit_name"] == "北京代表处")
    assert beijing["target_wan"] == 7000
    assert beijing["completion_pct"] == pytest.approx(37.82)
    assert results[5], "政企收入范围筛选应有数据可演示"
    assert all(3000 <= row["revenue_wan"] <= 5000 for row in results[5])
    assert sum(row["share_pct"] for row in results[5]) == pytest.approx(100, abs=0.03)
    assert len(results[6]) == 3
    assert sum(row["share_pct"] for row in results[6]) < 100
    assert {row["product_line"]: row["yoy_pct"] for row in results[7]} == {
        "通用计算": -47, "智能计算": -90, "存储": 5, "商业解决方案": 12,
    }
    assert [row["contract_wan"] for row in results[8]] == [800, 650, 900, 1000, 3680]
    assert all(row["contract_count"] == 2 for row in results[8])
    assert results[9] == [{"high_risk_project_count": 7}]
    assert [row["commercial_target_wan"] for row in results[10]] == [7950, 7070, 6460, 5560, 4090]
    assert sum(row["solution_target_wan"] for row in results[10]) == 4410
    assert [row["project_id"] for row in results[11]] == list(range(1, 8))
    assert all(row["data_as_of"] == "2026-05-31" for row in results[11])
    assert len(results[12]) == 12
    assert results[12][0]["commercial_completion_pct"] == pytest.approx(6.04)
    assert results[12][0]["solution_completion_pct"] == 28


def test_real_constraints_and_grains(db):
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE fact_sales_monthly SET product_id=999 WHERE sales_id=1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("UPDATE fact_sales_monthly SET revenue_amount=-1 WHERE sales_id=1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO fact_target_yearly SELECT * FROM fact_target_yearly LIMIT 1")
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO fact_project_snapshot SELECT * FROM fact_project_snapshot LIMIT 1")
    assert db.execute("SELECT COUNT(*) FROM dim_date").fetchone()[0] == 730
    assert db.execute("SELECT COUNT(*) FROM fact_sales_monthly").fetchone()[0] == 720
    assert db.execute("SELECT COUNT(*) FROM fact_contract_line").fetchone()[0] == 20
    assert db.execute("SELECT COUNT(*) FROM fact_project_snapshot").fetchone()[0] == 24


def test_latest_snapshot_before_risk_filter(db):
    # 项目 9 曾高风险，最新已降级；项目 8 最新已关闭，两者均不应计入。
    assert db.execute("SELECT risk_level FROM fact_project_snapshot WHERE project_id=9 ORDER BY snapshot_date_id").fetchall()[0][0] == "高风险"
    assert run(db, 9)[0]["high_risk_project_count"] == 7
    db.execute("UPDATE fact_project_snapshot SET risk_level='低风险' WHERE project_id=1 AND snapshot_date_id=20260531")
    assert run(db, 9)[0]["high_risk_project_count"] == 6


def test_zero_target_and_previous_period(db):
    db.execute("UPDATE fact_target_yearly SET revenue_target_amount=0 WHERE target_year=2026 AND business_unit_id=1")
    beijing = next(row for row in run(db, 4) if row["business_unit_name"] == "北京代表处")
    assert beijing["completion_pct"] is None
    db.execute("UPDATE fact_sales_monthly SET revenue_amount=0 WHERE month_date_id BETWEEN 20250101 AND 20251231")
    assert all(row["yoy_pct"] is None for row in run(db, 7))


def test_no_future_facts_or_target_multiplication(db):
    # 真正增加去年非同期月份，验证同比查询不会误用去年全年收入。
    db.execute("INSERT INTO fact_sales_monthly VALUES (9999,20251231,1,3,1,999999999,1)")
    assert {row["product_line"]: row["yoy_pct"] for row in run(db, 7)}["智能计算"] == -90
    assert db.execute("SELECT MAX(month_date_id) FROM fact_sales_monthly").fetchone()[0] == 20260531
    assert sum(row["target_wan"] for row in run(db, 4)) == 216000


def test_meta_config_covers_actual_schema_and_dependencies(db):
    config = yaml.safe_load((ROOT / "conf/meta_config.yaml").read_text(encoding="utf-8"))
    registered = {table["name"] for table in config["tables"]}
    actual = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert registered == actual - {"table_info", "column_info", "metric_info", "column_metric"}
    column_ids = set()
    for table in config["tables"]:
        name = table["name"]
        schema = db.execute(f"PRAGMA table_info({name})").fetchall()
        assert {column["name"] for column in table["columns"]} == {row[1] for row in schema}
        foreign_columns = {row[3] for row in db.execute(f"PRAGMA foreign_key_list({name})")}
        assert foreign_columns == {column["name"] for column in table["columns"] if column["role"] == "foreign_key"}
        db.execute("INSERT INTO table_info VALUES (?,?,?,?)", (name, name, table["role"], table["description"]))
        sql_types = {row[1]: row[2] for row in schema}
        for column in table["columns"]:
            column_id = name + "." + column["name"]
            column_ids.add(column_id)
            db.execute("INSERT INTO column_info VALUES (?,?,?,?,?,?,?,?)", (
                column_id, column["name"], sql_types[column["name"]], column["role"], "[]",
                column["description"], json.dumps(column["alias"], ensure_ascii=False), name,
            ))
    assert max(map(len, column_ids)) <= 128
    for metric in config["metrics"]:
        assert set(metric["relevant_columns"]) <= column_ids
        db.execute("INSERT INTO metric_info VALUES (?,?,?,?,?)", (
            metric["name"], metric["name"], metric["description"],
            json.dumps(metric["relevant_columns"]), json.dumps(metric["alias"]),
        ))
        for column_id in metric["relevant_columns"]:
            db.execute("INSERT INTO column_metric VALUES (?,?)", (column_id, metric["name"]))
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("INSERT INTO column_metric VALUES ('missing.column', ?)", (config["metrics"][0]["name"],))
    assert db.execute("PRAGMA foreign_key_check").fetchall() == []


def test_metadata_samples_are_json_serializable_without_precision_loss():
    result = Mock()
    result.fetchall.return_value = [
        (date(2026, 5, 31),), (datetime(2026, 5, 31, 12, 30),),
        (Decimal("9999999999999999.99"),), (12,), (None,), ("高风险",),
    ]
    session = Mock()
    session.execute = AsyncMock(return_value=result)
    values = asyncio.run(DWMySQLRepository(session).get_column_values("demo", "value"))
    assert json.loads(json.dumps(values)) == [
        "2026-05-31", "2026-05-31T12:30:00", "9999999999999999.99", 12, None, "高风险",
    ]


def test_meta_orm_matches_sql_constraints(db):
    for model in (TableInfoMySQL, ColumnInfoMySQL, MetricInfoMySQL, ColumnMetricMySQL):
        table = model.__table__
        schema = db.execute(f"PRAGMA table_info({table.name})").fetchall()
        assert {c.name for c in table.columns} == {row[1] for row in schema}
        assert [c.name for c in table.primary_key] == [row[1] for row in sorted(schema, key=lambda row: row[5]) if row[5]]
        assert all(not c.nullable for c in table.columns)
        assert all(row[3] for row in schema)
        expected_fks = {(fk.parent.name, fk.column.table.name, fk.column.name) for fk in table.foreign_keys}
        actual_fks = {(row[3], row[2], row[4]) for row in db.execute(f"PRAGMA foreign_key_list({table.name})")}
        assert expected_fks == actual_fks
        expected_uniques = {tuple(c.name for c in constraint.columns) for constraint in table.constraints if isinstance(constraint, UniqueConstraint)}
        actual_uniques = {
            tuple(row[2] for row in db.execute(f"PRAGMA index_info({index[1]})"))
            for index in db.execute(f"PRAGMA index_list({table.name})") if index[3] == "u"
        }
        assert expected_uniques == actual_uniques
