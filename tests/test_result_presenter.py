"""展示层验证真实汇总、金额单位、比例、空结果与实际表引用。"""
from app.services.result_presenter import build_presentation


def test_top5_totals_are_actual_not_twelve_percent():
    rows = [{"经营单元": name, "年度": 2026, "商业目标": a, "商解目标": b} for name, a, b in
            [("北京", 7950, 1200), ("上海", 7070, 980), ("浙江", 6460, 860), ("江苏", 5560, 720), ("山东", 4090, 650)]]
    sql = "SELECT u.business_unit_name AS 经营单元, t.target_year AS 年度, t.commercial_target_amount/10000 AS 商业目标, t.solution_target_amount/10000 AS 商解目标 FROM fact_target_yearly t JOIN dim_business_unit u ON u.business_unit_id=t.business_unit_id WHERE t.target_year=2026 ORDER BY 商业目标 DESC LIMIT 5"
    result = build_presentation("商业目标TOP5", sql, rows)
    assert result["tables"] == ["dim_business_unit", "fact_target_yearly"]
    assert result["statistics"][0]["total"] == 31130
    assert result["statistics"][1]["total"] == 4410
    assert result["columns"][1]["kind"] == "dimension"
    assert result["columns"][2]["unit"] == "万元"


def test_ratio_not_summed_and_cte_not_a_real_table():
    sql = "WITH actual AS (SELECT business_unit_id, SUM(revenue_amount) AS revenue_amount FROM fact_sales_monthly GROUP BY business_unit_id) SELECT business_unit_id, 100*revenue_amount/revenue_target_amount AS completion_pct FROM actual JOIN fact_target_yearly USING(business_unit_id)"
    result = build_presentation("收入完成率", sql, [{"business_unit_id": 1, "completion_pct": 30.5}])
    assert result["tables"] == ["fact_sales_monthly", "fact_target_yearly"]
    assert result["statistics"][0]["total"] is None
    assert result["columns"][1]["unit"] == "%"


def test_empty_rows_and_suggestions_keep_context():
    empty = build_presentation("北京收入", "SELECT revenue_amount FROM fact_sales_monthly WHERE 1=0", [])
    assert empty["chart"] is None
    assert empty["suggestions"] == []
    result = build_presentation("北京2026年1至5月收入", "SELECT business_unit_id, revenue_amount FROM fact_sales_monthly", [{"business_unit_id": 1, "revenue_amount": 100}])
    assert all("北京2026年1至5月收入" in q for q in result["suggestions"])


def test_count_is_a_metric_and_average_is_not_additive():
    count = build_presentation("有多少项目", "SELECT COUNT(project_id) AS 项目数 FROM fact_project_snapshot", [{"项目数": 7}])
    assert count["columns"][0]["kind"] == "metric"
    average = build_presentation("平均收入", "SELECT AVG(revenue_amount)/10000 AS 平均收入 FROM fact_sales_monthly", [{"平均收入": 30.5}])
    assert average["statistics"][0]["total"] is None
