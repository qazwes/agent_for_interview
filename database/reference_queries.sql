-- Q1：2026 年各产品线收入与销量；金额展示为万元。
SELECT p.product_line, ROUND(SUM(s.revenue_amount) / 10000.0, 2) AS revenue_wan,
       SUM(s.sales_quantity) AS sales_quantity
FROM fact_sales_monthly s
JOIN dim_date d ON d.date_id = s.month_date_id
JOIN dim_product p ON p.product_id = s.product_id
WHERE d.year = 2026
GROUP BY p.product_line
ORDER BY revenue_wan DESC;

-- Q2：北京的产品线收入情况，使用驻地城市筛选。
SELECT p.product_line, ROUND(SUM(s.revenue_amount) / 10000.0, 2) AS revenue_wan
FROM fact_sales_monthly s
JOIN dim_date d ON d.date_id = s.month_date_id
JOIN dim_business_unit u ON u.business_unit_id = s.business_unit_id
JOIN dim_product p ON p.product_id = s.product_id
WHERE d.year = 2026 AND u.city = '北京'
GROUP BY p.product_line
ORDER BY revenue_wan DESC;

-- Q3：深圳的产品型号销量及收入。
SELECT p.product_model, SUM(s.sales_quantity) AS sales_quantity,
       ROUND(SUM(s.revenue_amount) / 10000.0, 2) AS revenue_wan
FROM fact_sales_monthly s
JOIN dim_date d ON d.date_id = s.month_date_id
JOIN dim_business_unit u ON u.business_unit_id = s.business_unit_id
JOIN dim_product p ON p.product_id = s.product_id
WHERE d.year = 2026 AND u.city = '深圳'
GROUP BY p.product_model
ORDER BY sales_quantity DESC;

-- Q4：经营单元收入完成率；先汇总收入，再连接全年收入目标。
WITH actual AS (
    SELECT s.business_unit_id, SUM(s.revenue_amount) AS revenue_amount
    FROM fact_sales_monthly s
    JOIN dim_date d ON d.date_id = s.month_date_id
    WHERE d.year = 2026
    GROUP BY s.business_unit_id
)
SELECT u.business_unit_name,
       ROUND(COALESCE(a.revenue_amount, 0) / 10000.0, 2) AS revenue_wan,
       ROUND(t.revenue_target_amount / 10000.0, 2) AS target_wan,
       ROUND(100.0 * COALESCE(a.revenue_amount, 0) / NULLIF(t.revenue_target_amount, 0), 2) AS completion_pct
FROM fact_target_yearly t
JOIN dim_business_unit u ON u.business_unit_id = t.business_unit_id
LEFT JOIN actual a ON a.business_unit_id = t.business_unit_id
WHERE t.target_year = 2026
ORDER BY revenue_wan DESC;

-- Q5：政企大类收入 3000万-5000万的经营单元，按筛选后合计计算饼图占比。
WITH eligible AS (
    SELECT u.business_unit_name, SUM(s.revenue_amount) AS revenue_amount
    FROM fact_sales_monthly s
    JOIN dim_date d ON d.date_id = s.month_date_id
    JOIN dim_business_unit u ON u.business_unit_id = s.business_unit_id
    JOIN dim_industry i ON i.industry_id = s.industry_id
    WHERE d.year = 2026 AND i.industry_category = '政企'
    GROUP BY u.business_unit_name
    HAVING SUM(s.revenue_amount) BETWEEN 30000000 AND 50000000
)
SELECT business_unit_name, ROUND(revenue_amount / 10000.0, 2) AS revenue_wan,
       ROUND(100.0 * revenue_amount / NULLIF(SUM(revenue_amount) OVER (), 0), 2) AS share_pct
FROM eligible
ORDER BY revenue_amount DESC;

-- Q6：按销售额排名 TOP3 产品型号；占比的分母为全部产品收入。
WITH product_revenue AS (
    SELECT p.product_model, SUM(s.revenue_amount) AS revenue_amount
    FROM fact_sales_monthly s
    JOIN dim_date d ON d.date_id = s.month_date_id
    JOIN dim_product p ON p.product_id = s.product_id
    WHERE d.year = 2026
    GROUP BY p.product_model
)
SELECT product_model, ROUND(revenue_amount / 10000.0, 2) AS revenue_wan,
       ROUND(100.0 * revenue_amount / NULLIF(SUM(revenue_amount) OVER (), 0), 2) AS share_pct
FROM product_revenue
ORDER BY revenue_amount DESC
LIMIT 3;

-- Q7：各产品线同比，比较相同的 1-5 月，去年为零时返回 NULL。
WITH periods AS (
    SELECT p.product_line,
           SUM(CASE WHEN d.year = 2026 THEN s.revenue_amount ELSE 0 END) AS current_amount,
           SUM(CASE WHEN d.year = 2025 THEN s.revenue_amount ELSE 0 END) AS previous_amount
    FROM fact_sales_monthly s
    JOIN dim_date d ON d.date_id = s.month_date_id
    JOIN dim_product p ON p.product_id = s.product_id
    WHERE d.year IN (2025, 2026) AND d.month BETWEEN 1 AND 5
    GROUP BY p.product_line
)
SELECT product_line, ROUND(current_amount / 10000.0, 2) AS current_wan,
       ROUND(previous_amount / 10000.0, 2) AS previous_wan,
       ROUND(100.0 * (current_amount - previous_amount) / NULLIF(previous_amount, 0), 2) AS yoy_pct
FROM periods
ORDER BY product_line;

-- Q8：2026 年每月实际签约金额；合同明细金额不因快照而重复。
SELECT d.month, ROUND(SUM(c.contract_amount) / 10000.0, 2) AS contract_wan,
       COUNT(DISTINCT c.contract_no) AS contract_count
FROM fact_contract_line c
JOIN dim_date d ON d.date_id = c.signed_date_id
WHERE d.year = 2026
GROUP BY d.month
ORDER BY d.month;

-- Q9：当前高风险项目数；先在所有状态中找每个项目最新快照，再筛选。
WITH latest AS (
    SELECT project_id, MAX(snapshot_date_id) AS snapshot_date_id
    FROM fact_project_snapshot
    GROUP BY project_id
)
SELECT COUNT(DISTINCT s.project_id) AS high_risk_project_count
FROM fact_project_snapshot s
JOIN latest l ON l.project_id = s.project_id AND l.snapshot_date_id = s.snapshot_date_id
WHERE s.is_active = 1 AND s.risk_level = '高风险';

-- Q10：原型商业目标 TOP5，商解目标读取自身字段，不由商业目标乘比例推算。
SELECT u.business_unit_name, t.target_year,
       ROUND(t.commercial_target_amount / 10000.0, 2) AS commercial_target_wan,
       ROUND(t.solution_target_amount / 10000.0, 2) AS solution_target_wan
FROM fact_target_yearly t
JOIN dim_business_unit u ON u.business_unit_id = t.business_unit_id
WHERE t.target_year = 2026
ORDER BY t.commercial_target_amount DESC
LIMIT 5;

-- Q11：当前高风险项目明细；已完成项目和历史降级项目均不包含。
WITH latest AS (
    SELECT project_id, MAX(snapshot_date_id) AS snapshot_date_id
    FROM fact_project_snapshot
    GROUP BY project_id
)
SELECT p.project_id, p.project_name, p.customer_name, u.business_unit_name,
       d.calendar_date AS data_as_of, s.project_stage, s.risk_level, s.risk_description
FROM fact_project_snapshot s
JOIN latest l ON l.project_id = s.project_id AND l.snapshot_date_id = s.snapshot_date_id
JOIN dim_project p ON p.project_id = s.project_id
JOIN dim_business_unit u ON u.business_unit_id = s.business_unit_id
JOIN dim_date d ON d.date_id = s.snapshot_date_id
WHERE s.is_active = 1 AND s.risk_level = '高风险'
ORDER BY p.project_id;

-- Q12：商业完成率与商解完成率分别使用签约额、商解收入。
WITH signed AS (
    SELECT c.business_unit_id, SUM(c.contract_amount) AS signed_amount
    FROM fact_contract_line c
    JOIN dim_date d ON d.date_id = c.signed_date_id
    WHERE d.year = 2026
    GROUP BY c.business_unit_id
), solution AS (
    SELECT s.business_unit_id, SUM(s.revenue_amount) AS solution_amount
    FROM fact_sales_monthly s
    JOIN dim_date d ON d.date_id = s.month_date_id
    JOIN dim_product p ON p.product_id = s.product_id
    WHERE d.year = 2026 AND p.product_line = '商业解决方案'
    GROUP BY s.business_unit_id
)
SELECT u.business_unit_name,
       ROUND(100.0 * COALESCE(c.signed_amount, 0) / NULLIF(t.commercial_target_amount, 0), 2) AS commercial_completion_pct,
       ROUND(100.0 * COALESCE(s.solution_amount, 0) / NULLIF(t.solution_target_amount, 0), 2) AS solution_completion_pct
FROM fact_target_yearly t
JOIN dim_business_unit u ON u.business_unit_id = t.business_unit_id
LEFT JOIN signed c ON c.business_unit_id = t.business_unit_id
LEFT JOIN solution s ON s.business_unit_id = t.business_unit_id
WHERE t.target_year = 2026
ORDER BY u.business_unit_id;
