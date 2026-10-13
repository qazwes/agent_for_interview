"""生成简化销售经管 DW、元数据配置和表结构说明；不连接数据库。

从 my-agent 目录运行：python -m app.scripts.generate_demo_warehouse
SQL 用于空 Docker 数据卷初始化，样例为确定性的合成数据。
"""

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Column:
    name: str
    sql_type: str
    role: str
    description: str
    alias: list[str] = field(default_factory=list)
    sync: bool = False
    reference: tuple[str, str] | None = None
    nullable: bool = False


@dataclass
class Table:
    name: str
    role: str
    grain: str
    description: str
    columns: list[Column]
    primary_key: tuple[str, ...]
    constraints: list[str] = field(default_factory=list)


def col(name, sql_type, role, description, alias=(), sync=False, reference=None, nullable=False):
    return Column(name, sql_type, role, description, list(alias), sync, reference, nullable)


def fk(name, target, description, alias=(), nullable=False):
    return col(name, "INT", "foreign_key", f"{description}；关联 {target}.{name}。", alias,
               reference=(target, name), nullable=nullable)


TABLES = [
    Table("dim_date", "dim", "一自然日一行", "日期维度；date_id 为 YYYYMMDD。分析月份/季度从此表分组；已确认收入数据截止 2026-05-31。", [
        col("date_id", "INT", "primary_key", "日期编码 YYYYMMDD。", ["日期ID"]),
        col("calendar_date", "DATE", "dimension", "自然日期。", ["日期", "时间"]),
        col("year", "SMALLINT", "dimension", "自然年。年度目标以 target_year 直接关联此年份，不按每一天连接目标。", ["年度", "年份", "年"], True),
        col("quarter", "TINYINT", "dimension", "季度，1 至 4。", ["季度"], True),
        col("month", "TINYINT", "dimension", "月份，1 至 12。", ["月份", "月"], True),
        col("day", "TINYINT", "dimension", "日，1 至 31。", ["日"]),
    ], ("date_id",), ["UNIQUE KEY uq_calendar_date (calendar_date)", "CHECK (quarter BETWEEN 1 AND 4)", "CHECK (month BETWEEN 1 AND 12)", "CHECK (day BETWEEN 1 AND 31)"]),
    Table("dim_business_unit", "dim", "一经营单元一行", "经营单元维度，合并省份/城市/区域属性。北京、深圳等城市筛选使用 city；代表处名称使用 business_unit_name。", [
        col("business_unit_id", "INT", "primary_key", "经营单元唯一编号。", ["经营单元ID"]),
        col("business_unit_name", "VARCHAR(80)", "dimension", "经营单元全称，如北京代表处、川藏代表处。", ["经营单元", "代表处", "办事处"], True),
        col("province", "VARCHAR(40)", "dimension", "所属省级区域；川藏为简化区域名称。", ["省份", "省"], True),
        col("city", "VARCHAR(40)", "dimension", "经营单元驻地城市。", ["城市", "北京", "深圳"], True),
        col("region_name", "VARCHAR(40)", "dimension", "销售大区，如华北、华东、华南。", ["大区", "区域", "地区"], True),
    ], ("business_unit_id",), ["UNIQUE KEY uq_unit_name (business_unit_name)"]),
    Table("dim_product", "dim", "一产品型号一行", "产品维度；产品线作为属性直接保存在本表，避免增加产品线维表。销售/合同通过 product_id 关联本表。", [
        col("product_id", "INT", "primary_key", "产品唯一编号。", ["产品ID"]),
        col("product_model", "VARCHAR(80)", "dimension", "产品型号，如 R5300 G5；不等同于产品线。", ["产品型号", "型号", "产品名称"], True),
        col("product_line", "VARCHAR(40)", "dimension", "通用计算、智能计算、存储、商业解决方案。政企解决方案在本 demo 归入商业解决方案。", ["产品线", "商解", "政企解决方案"], True),
        col("product_type", "VARCHAR(40)", "dimension", "产品类型，如服务器、存储、解决方案。", ["产品类型"], True),
        col("is_new_product", "TINYINT", "dimension", "是否新产品，1 是，0 否。", ["新产品", "是否为新产品"], True),
    ], ("product_id",), ["UNIQUE KEY uq_product_model (product_model)", "CHECK (is_new_product IN (0, 1))"]),
    Table("dim_industry", "dim", "一行业小类一行", "行业维度，行业大类和行业名称同时保留。原型的政企筛选对应 industry_category='政企'，不能把政企当作所有行业的小类名称。", [
        col("industry_id", "INT", "primary_key", "行业唯一编号。", ["行业ID"]),
        col("industry_category", "VARCHAR(40)", "dimension", "行业大类：政企、商业市场、运营商。", ["行业大类", "政企"], True),
        col("industry_name", "VARCHAR(40)", "dimension", "行业小类，如数字政府、金融、互联网。", ["行业", "行业小类", "细分行业"], True),
    ], ("industry_id",), ["UNIQUE KEY uq_industry (industry_category, industry_name)"]),
    Table("dim_project", "dim", "一项目一行", "PPL 项目基础信息；风险和阶段保存于 fact_project_snapshot，实际合同保存于 fact_contract_line。项目可能尚未签约或拥有多条合同明细。", [
        col("project_id", "INT", "primary_key", "项目唯一编号。", ["项目ID"]),
        col("opportunity_no", "VARCHAR(40)", "dimension", "预销售/机会点编号。", ["机会点编号", "预销售编号"], True),
        col("project_name", "VARCHAR(120)", "dimension", "项目名称。", ["项目名称", "项目"], True),
        col("customer_name", "VARCHAR(120)", "dimension", "最终客户名称，简化为项目属性。", ["最终客户", "客户名称"], True),
        col("sales_owner", "VARCHAR(40)", "dimension", "项目销售负责人。", ["销售", "负责人"], True),
    ], ("project_id",), ["UNIQUE KEY uq_opportunity (opportunity_no)"]),
    Table("fact_sales_monthly", "fact", "一月份 × 经营单元 × 产品型号 × 行业一行", "月度已确认收入及销量；month_date_id 是月末 date_id，关联 dim_date.date_id。只保存已发生的当月增量，不存累计数。金额为不含税人民币元；截止 2026-05-31，有 2025/2026 年同期间数据。", [
        col("sales_id", "BIGINT", "primary_key", "月度销售事实唯一编号。", ["销售记录ID"]),
        col("month_date_id", "INT", "foreign_key", "收入/销量归属月的月末日期；关联 dim_date.date_id。", ["收入月份", "销售日期"], reference=("dim_date", "date_id")),
        fk("business_unit_id", "dim_business_unit", "收入归属经营单元", ["经营单元ID"]),
        fk("product_id", "dim_product", "收入归属产品型号", ["产品ID"]),
        fk("industry_id", "dim_industry", "客户行业", ["行业ID"]),
        col("revenue_amount", "DECIMAL(18,2)", "measure", "当月已确认不含税收入，单位元。销售额默认使用此字段；不是合同签约额。", ["收入", "收入额", "销售额", "销售总额"]),
        col("sales_quantity", "INT", "measure", "当月销售数量，单位台套。销售最多按数量排名；按销售额排名需使用 revenue_amount。", ["销量", "销售数量", "台套数"]),
    ], ("sales_id",), ["UNIQUE KEY uq_sales_grain (month_date_id, business_unit_id, product_id, industry_id)", "CHECK (revenue_amount >= 0)", "CHECK (sales_quantity >= 0)"]),
    Table("fact_target_yearly", "fact", "一年度 × 经营单元一行", "年度目标；联合主键 target_year/business_unit_id。商业目标=不含税签约额，商解目标=商业解决方案不含税收入；原型未明确收入完成率分母，另设 revenue_target_amount 作为总收入目标。无产品线/行业目标粒度，不能把全单元目标当成某产品线目标。", [
        col("target_year", "SMALLINT", "primary_key", "目标年度，也是联合主键的一部分。与汇总收入年份匹配，不关联 dim_date 每一天。", ["目标年度", "年度"], True),
        fk("business_unit_id", "dim_business_unit", "联合主键另一部分，目标所属经营单元", ["经营单元ID"]),
        col("commercial_target_amount", "DECIMAL(18,2)", "measure", "全年不含税签约额目标，元。原型商业目标(万元)乘 10000 后入库。", ["商业目标", "签约目标"]),
        col("solution_target_amount", "DECIMAL(18,2)", "measure", "全年商业解决方案产品线不含税收入目标，元。", ["商解目标", "商业解决方案目标"]),
        col("revenue_target_amount", "DECIMAL(18,2)", "measure", "全年总收入目标，元；为收入完成率明确补充的 demo 假设，不等同于商业目标。", ["收入目标", "年度收入目标"]),
    ], ("target_year", "business_unit_id"), ["CHECK (target_year BETWEEN 2000 AND 2100)", "CHECK (commercial_target_amount >= 0)", "CHECK (solution_target_amount >= 0)", "CHECK (revenue_target_amount >= 0)"]),
    Table("fact_contract_line", "fact", "一合同 × 明细行一行", "实际已签约合同明细；contract_no/line_no 唯一，合同可有多个产品。金额为该行不含税元，不能在每一行重复存合同总额；合同数 COUNT(DISTINCT contract_no)。通过 signed_date_id 统计签约月份，不用项目快照月份代替。", [
        col("contract_line_id", "BIGINT", "primary_key", "合同明细唯一编号。", ["合同明细ID"]),
        col("contract_no", "VARCHAR(40)", "dimension", "合同编号；同一合同在不同明细行重复出现。", ["合同编号", "合同号"], True),
        col("line_no", "SMALLINT", "dimension", "合同内明细行号。", ["行号"]),
        fk("project_id", "dim_project", "合同关联项目", ["项目ID"]),
        col("signed_date_id", "INT", "foreign_key", "合同实际签订日期；关联 dim_date.date_id。", ["合同签订日期", "签订时间"], reference=("dim_date", "date_id")),
        fk("business_unit_id", "dim_business_unit", "合同签约业绩归属经营单元", ["经营单元ID"]),
        fk("product_id", "dim_product", "合同明细产品型号", ["产品ID"]),
        fk("industry_id", "dim_industry", "合同客户行业", ["行业ID"]),
        col("contract_quantity", "INT", "measure", "本合同明细的签约数量；不等同于当月确认销量。", ["签约数量", "合同台套数"]),
        col("contract_amount", "DECIMAL(18,2)", "measure", "本明细不含税签约金额，元；月度合同趋势及商业完成率使用此字段。", ["合同金额", "不含税金额", "签约额"]),
    ], ("contract_line_id",), ["UNIQUE KEY uq_contract_line (contract_no, line_no)", "CHECK (contract_quantity > 0)", "CHECK (contract_amount >= 0)"]),
    Table("fact_project_snapshot", "fact", "一快照日期 × 项目一行", "PPL 项目阶段与风险快照。联合主键 snapshot_date_id/project_id。快照不是事件流水，同一项目多个快照不能累加。当前风险须先取每个项目最近一条快照，再筛选 is_active=1 和风险等级。最新演示快照 2026-05-31。", [
        col("snapshot_date_id", "INT", "foreign_key", "风险状态观察日期，联合主键的一部分；关联 dim_date.date_id。", ["快照日期", "数据截止日期"], reference=("dim_date", "date_id")),
        fk("project_id", "dim_project", "联合主键另一部分，观察项目", ["项目ID"]),
        fk("business_unit_id", "dim_business_unit", "快照时项目所属经营单元", ["经营单元ID"]),
        fk("industry_id", "dim_industry", "快照时项目客户行业", ["行业ID"]),
        col("project_stage", "VARCHAR(20)", "dimension", "商机、方案、投标、商务、签约、交付、完成。", ["项目阶段", "阶段"], True),
        col("risk_level", "VARCHAR(20)", "dimension", "项目整体风险等级：低风险、中风险、高风险。", ["项目风险等级", "风险等级", "高风险项目"], True),
        col("competition_risk", "VARCHAR(20)", "dimension", "竞争风险等级。", ["项目竞争风险"], True),
        col("signing_risk", "VARCHAR(20)", "dimension", "合同签订风险等级。", ["合同签订风险"], True),
        col("delivery_risk", "VARCHAR(20)", "dimension", "供应与交付风险等级。", ["供应风险", "交付风险"], True),
        col("is_active", "TINYINT", "dimension", "是否仍在跟进，1 是；完成/关闭项目为 0，默认当前风险统计排除。", ["在跟进", "活跃项目"], True),
        col("risk_description", "VARCHAR(255)", "dimension", "项目进展及风险说明，不据此生成无数据依据的预测。", ["项目进展", "风险说明"]),
    ], ("snapshot_date_id", "project_id"), ["CHECK (is_active IN (0, 1))", *[f"CHECK ({name} IN ('低风险', '中风险', '高风险'))" for name in ("risk_level", "competition_risk", "signing_risk", "delivery_risk")]]),
]


def metric(name, description, columns, aliases):
    return {"name": name, "description": description, "relevant_columns": columns, "alias": aliases}


METRICS = [
    metric("销售收入", "SUM(fact_sales_monthly.revenue_amount)，不含税人民币元；万元展示除以 10000。按月份/经营单元/产品线/行业统计已确认收入，不能用签约额替代。", ["fact_sales_monthly.revenue_amount"], ["收入", "收入额", "销售额", "销售总额"]),
    metric("销售数量", "SUM(fact_sales_monthly.sales_quantity)，单位台套。销售最多默认按销量排名，按金额排名须明确使用销售收入。", ["fact_sales_monthly.sales_quantity"], ["销量", "台套数", "销售最多"]),
    metric("合同签约额", "SUM(fact_contract_line.contract_amount)，不含税元；按 dim_date 对 signed_date_id 的年份/月份分组生成合同趋势，不从风险快照取合同金额。", ["fact_contract_line.contract_amount", "fact_contract_line.signed_date_id"], ["合同金额", "签约额", "合同金额趋势"]),
    metric("合同数量", "COUNT(DISTINCT fact_contract_line.contract_no)。合同有多条产品明细，COUNT(*) 是明细数而不是合同数。", ["fact_contract_line.contract_no"], ["合同数", "签约合同数"]),
    metric("商业目标", "SUM(fact_target_yearly.commercial_target_amount)，指定年度的全经营单元不含税签约目标，元。", ["fact_target_yearly.commercial_target_amount", "fact_target_yearly.target_year"], ["签约目标", "年度商业目标"]),
    metric("商解目标", "SUM(fact_target_yearly.solution_target_amount)，指定年度商业解决方案产品线不含税收入目标，元。", ["fact_target_yearly.solution_target_amount", "fact_target_yearly.target_year"], ["商业解决方案目标"]),
    metric("收入目标", "SUM(fact_target_yearly.revenue_target_amount)，指定年度全经营单元总收入目标，元。原型未明确此分母，demo 单独定义，不使用商业签约目标代替。", ["fact_target_yearly.revenue_target_amount", "fact_target_yearly.target_year"], ["年度收入目标"]),
    metric("收入完成率", "已确认收入 / NULLIF(年度收入目标,0) * 100。先将月度收入按年度/经营单元汇总，再与 fact_target_yearly 关联；多单元整体完成率用总收入/总目标，不能平均行比例或把目标 JOIN 到每条收入明细后重复求和。默认截至 2026-05-31，对比全年目标；本库无单独的行业/产品线收入目标。", ["fact_sales_monthly.revenue_amount", "fact_sales_monthly.month_date_id", "fact_target_yearly.revenue_target_amount", "fact_target_yearly.target_year", "fact_target_yearly.business_unit_id"], ["完成率", "目标达成率", "收入达成"]),
    metric("商业完成率", "不含税合同签约额 / NULLIF(全年商业目标,0) * 100。合同和目标先按年度/经营单元分别聚合后关联。", ["fact_contract_line.contract_amount", "fact_contract_line.signed_date_id", "fact_target_yearly.commercial_target_amount", "fact_target_yearly.target_year", "fact_target_yearly.business_unit_id"], ["签约达成率", "商业达成率"]),
    metric("商解完成率", "仅 dim_product.product_line='商业解决方案' 的收入 / NULLIF(全年商解目标,0) * 100，按年度/经营单元先聚合再关联。", ["fact_sales_monthly.revenue_amount", "dim_product.product_line", "fact_target_yearly.solution_target_amount", "fact_target_yearly.target_year", "fact_target_yearly.business_unit_id"], ["商解达成率"]),
    metric("收入同比", "(本期收入-上年同期收入)/NULLIF(上年同期收入,0)*100；按同一维度和同一月份范围比较。2026 年数据截至 5 月，默认比较 2025 年 1-5 月；不能拿今年部分月份比较去年全年。", ["fact_sales_monthly.revenue_amount", "fact_sales_monthly.month_date_id", "dim_date.year", "dim_date.month"], ["同比", "同比变化", "增长率", "下滑趋势"]),
    metric("收入占比", "分组收入/NULLIF(同一筛选范围总收入,0)*100。原型政企 3000万-5000万筛选在 GROUP BY 后用 HAVING；饼图默认以筛选后保留经营单元合计为分母。产品 TOP3 占比默认以全部产品收入为分母，再取 TOP3。", ["fact_sales_monthly.revenue_amount"], ["收入占比", "销售额占比", "饼图占比"]),
    metric("当前高风险项目数", "先按 project_id 取 fact_project_snapshot 最近快照，随后筛选 is_active=1 AND risk_level='高风险'，COUNT(DISTINCT project_id)。不能累计历史快照，也不能先筛高风险再取最近快照；演示最新数据截止 2026-05-31。", ["fact_project_snapshot.project_id", "fact_project_snapshot.snapshot_date_id", "fact_project_snapshot.risk_level", "fact_project_snapshot.is_active"], ["高风险项目", "高风险项目数量", "目前有多少高风险项目"]),
]


UNITS = [
    (1, "北京代表处", "北京", "北京", "华北"), (2, "上海代表处", "上海", "上海", "华东"),
    (3, "浙江代表处", "浙江", "杭州", "华东"), (4, "江苏代表处", "江苏", "南京", "华东"),
    (5, "山东代表处", "山东", "济南", "华东"), (6, "深圳代表处", "广东", "深圳", "华南"),
    (7, "广州代表处", "广东", "广州", "华南"), (8, "江西办事处", "江西", "南昌", "华东"),
    (9, "福建代表处", "福建", "福州", "华东"), (10, "新疆代表处", "新疆", "乌鲁木齐", "西北"),
    (11, "安徽办事处", "安徽", "合肥", "华东"), (12, "川藏代表处", "川藏", "成都", "西南"),
]
PRODUCTS = [
    (1, "R5300 G5", "通用计算", "服务器", 0), (2, "R5500 G5", "通用计算", "服务器", 0),
    (3, "R5900 G5", "智能计算", "服务器", 1), (4, "R2900 G5", "通用计算", "服务器", 0),
    (5, "R5200 G4", "存储", "存储", 0), (6, "政企云解决方案", "商业解决方案", "解决方案", 1),
]
INDUSTRIES = [(1, "政企", "数字政府"), (2, "政企", "金融"), (3, "政企", "教育"),
              (4, "商业市场", "互联网"), (5, "商业市场", "智能制造"), (6, "运营商", "通信")]


def demo_rows() -> dict[str, list[tuple]]:
    """生成固定样例；相同版本每次输出相同，便于参考 SQL 验证。"""
    rows = {table.name: [] for table in TABLES}
    current = date(2025, 1, 1)
    while current <= date(2026, 12, 31):
        rows["dim_date"].append((int(current.strftime("%Y%m%d")), current.isoformat(), current.year,
                                 (current.month - 1) // 3 + 1, current.month, current.day))
        current += timedelta(days=1)
    rows["dim_business_unit"] = UNITS
    rows["dim_product"] = PRODUCTS
    rows["dim_industry"] = INDUSTRIES
    rows["dim_project"] = [(i, f"OPP-{2026}-{i:03d}", f"项目{i:02d}-服务器采购", f"演示客户{i:02d}", f"销售{(i-1)%4+1}") for i in range(1, 13)]

    base_amounts = [100, 80, 60, 40, 30, 20]
    yoy = {"通用计算": Decimal("0.53"), "智能计算": Decimal("0.10"), "存储": Decimal("1.05"), "商业解决方案": Decimal("1.12")}
    for year in (2025, 2026):
        for month in range(1, 6):
            date_id = year * 10000 + month * 100 + calendar.monthrange(year, month)[1]
            for unit in UNITS:
                for product, base in zip(PRODUCTS, base_amounts):
                    amount = Decimal(unit[0] * base * month * 10000)
                    if year == 2026:
                        amount *= yoy[product[2]]
                    quantity = unit[0] * (7 - product[0]) * month
                    rows["fact_sales_monthly"].append((len(rows["fact_sales_monthly"])+1, date_id,
                        unit[0], product[0], (unit[0]+product[0]-2)%6+1, amount.quantize(Decimal("0.01")), quantity))

    commercial = [7950, 7070, 6460, 5560, 4090, 3900, 3800, 3700, 3600, 3500, 3400, 3300]
    solution = [1200, 980, 860, 720, 650, 600, 550, 500, 450, 400, 350, 300]
    for year in (2025, 2026):
        for unit, commercial_goal, solution_goal in zip(UNITS, commercial, solution):
            factor = Decimal("0.90") if year == 2025 else Decimal("1.00")
            rows["fact_target_yearly"].append((year, unit[0], Decimal(commercial_goal*10000)*factor,
                Decimal(solution_goal*10000)*factor, Decimal((5000+unit[0]*2000)*10000)*factor))

    # 2026 年 1-5 月签约额（万元）：800、650、900、1000、3680。
    for month, amount in enumerate((800, 650, 900, 1000, 3680), start=1):
        for contract_index, contract_share in enumerate((Decimal("0.60"), Decimal("0.40"))):
            project_id = (month-1)*2+contract_index+1
            for line_no, line_share in enumerate((Decimal("0.70"), Decimal("0.30")), start=1):
                rows["fact_contract_line"].append((len(rows["fact_contract_line"])+1,
                    f"HT-2026-{project_id:03d}", line_no, project_id, 20260000+month*100+20,
                    project_id, (project_id+line_no-2)%6+1, (project_id-1)%6+1, project_id*line_no,
                    (Decimal(amount*10000)*contract_share*line_share).quantize(Decimal("0.01"))))

    for snapshot_id in (20260430, 20260531):
        for project_id in range(1, 13):
            latest = snapshot_id == 20260531
            active = 0 if latest and project_id == 8 else 1
            # 项目 9 由历史高风险降为中风险，验证先取最新快照再筛选。
            high = project_id <= 8 or (not latest and project_id == 9)
            level = "高风险" if high else ("中风险" if project_id <= 10 else "低风险")
            stage = "完成" if not active else ("交付" if project_id <= (10 if latest else 8) else "商务")
            rows["fact_project_snapshot"].append((snapshot_id, project_id, project_id, (project_id-1)%6+1,
                stage, level, "中风险" if high else "低风险", "低风险", level, active,
                "交付延迟或回款逾期，需跟进" if high else "项目按计划推进"))
    return rows


def literal(value) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_dw() -> str:
    lines = ["-- 由 app/scripts/generate_demo_warehouse.py 生成；用于空数据卷初始化。",
             "-- 确定性合成数据，不照搬原型相互矛盾的模拟结果。金额统一不含税人民币元。",
             "-- 收入数据截止 2026-05-31；日期维度覆盖完整 2025/2026 年，不代表未来已有收入。",
             "SET NAMES utf8mb4;", "CREATE DATABASE IF NOT EXISTS dw DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
             "GRANT SELECT ON dw.* TO 'HeJing'@'%';", "USE dw;", ""]
    # 子表先于父表删除；兼容尚未使用的新建库以及旧教学脚本的表名。
    for name in [t.name for t in reversed(TABLES)] + ["fact_order", "dim_customer", "dim_region"]:
        lines.append(f"DROP TABLE IF EXISTS `{name}`;")
    for table in TABLES:
        definitions = []
        for column in table.columns:
            null = "NULL" if column.nullable else "NOT NULL"
            definitions.append(f"    `{column.name}` {column.sql_type} {null} COMMENT {literal(column.description)}")
        definitions.append("    PRIMARY KEY (" + ", ".join(f"`{key}`" for key in table.primary_key) + ")")
        for column in table.columns:
            if column.reference:
                target, key = column.reference
                definitions.append(f"    FOREIGN KEY (`{column.name}`) REFERENCES `{target}` (`{key}`)")
        definitions.extend("    " + constraint for constraint in table.constraints)
        lines.extend(["", f"-- 粒度：{table.grain}", f"CREATE TABLE `{table.name}` (",
                      ",\n".join(definitions), f") ENGINE=InnoDB COMMENT={literal(table.description)};"])
    seed_rows = demo_rows()
    for table in TABLES:
        values = seed_rows[table.name]
        names = ", ".join(f"`{column.name}`" for column in table.columns)
        lines.extend(["", f"INSERT INTO `{table.name}` ({names}) VALUES",
                      ",\n".join("    (" + ", ".join(literal(value) for value in row) + ")" for row in values) + ";"])
    return "\n".join(lines) + "\n"


def render_meta_config() -> str:
    config = {"tables": [{"name": table.name, "role": table.role,
                "description": f"粒度：{table.grain}。{table.description}",
                "columns": [{"name": column.name, "role": column.role,
                    "description": column.description, "alias": column.alias, "sync": column.sync}
                    for column in table.columns]} for table in TABLES], "metrics": METRICS}
    return "# 由 app/scripts/generate_demo_warehouse.py 生成，与 dw.sql 保持一致。\n" + yaml.safe_dump(config, allow_unicode=True, sort_keys=False, width=110)


def render_meta_sql() -> str:
    return """-- 元数据空表初始化；业务定义来自 conf/meta_config.yaml。
-- metadata-init 从 DW 获取实际字段类型/示例后填充，避免重复预填。
SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT SELECT, INSERT, UPDATE, DELETE ON meta.* TO 'HeJing'@'%';
USE meta;

-- 有真实外键后必须先删除子表。
DROP TABLE IF EXISTS column_metric;
DROP TABLE IF EXISTS column_info;
DROP TABLE IF EXISTS metric_info;
DROP TABLE IF EXISTS table_info;

CREATE TABLE table_info (
    id VARCHAR(64) NOT NULL COMMENT '主键：DW 表名',
    name VARCHAR(128) NOT NULL COMMENT 'DW 表名，与 id 一致',
    role VARCHAR(32) NOT NULL COMMENT 'fact 事实表；dim 维度表',
    description TEXT NOT NULL COMMENT '粒度、用途、关联、统计截止日期及业务限制',
    PRIMARY KEY (id),
    UNIQUE KEY uq_meta_table_name (name),
    CHECK (role IN ('fact', 'dim'))
) ENGINE=InnoDB COMMENT='表元数据，不保存真实收入或合同记录';

CREATE TABLE column_info (
    id VARCHAR(128) NOT NULL COMMENT '主键：DW 表名.字段名',
    name VARCHAR(128) NOT NULL COMMENT '真实字段名',
    type VARCHAR(64) NOT NULL COMMENT '从 DW 读取的字段类型',
    role VARCHAR(32) NOT NULL COMMENT '主键、外键、度量或维度角色；联合主键成员说明写入 description',
    examples JSON NOT NULL COMMENT '从 DW 抽取的真实样例值数组',
    description TEXT NOT NULL COMMENT '字段含义、单位、外键目标及口径',
    alias JSON NOT NULL COMMENT '业务别名数组',
    table_id VARCHAR(64) NOT NULL COMMENT '外键：所属 table_info.id',
    PRIMARY KEY (id),
    UNIQUE KEY uq_meta_column (table_id, name),
    FOREIGN KEY (table_id) REFERENCES table_info (id),
    CHECK (role IN ('primary_key', 'foreign_key', 'measure', 'dimension'))
) ENGINE=InnoDB COMMENT='字段元数据，字段 ID 扩展为 128 字符';

CREATE TABLE metric_info (
    id VARCHAR(64) NOT NULL COMMENT '主键：指标名称，与构建脚本保持一致',
    name VARCHAR(128) NOT NULL COMMENT '指标名称，如销售收入、收入完成率',
    description TEXT NOT NULL COMMENT '计算公式、单位、时间范围及跨事实表聚合规则',
    relevant_columns JSON NOT NULL COMMENT '依赖字段 ID 数组，实际关系由 column_metric 约束',
    alias JSON NOT NULL COMMENT '指标别名数组',
    PRIMARY KEY (id),
    UNIQUE KEY uq_meta_metric_name (name)
) ENGINE=InnoDB COMMENT='指标元数据；替换教学 GMV/AOV 为销售经管口径';

CREATE TABLE column_metric (
    column_id VARCHAR(128) NOT NULL COMMENT '外键：column_info.id',
    metric_id VARCHAR(64) NOT NULL COMMENT '外键：metric_info.id',
    PRIMARY KEY (column_id, metric_id),
    FOREIGN KEY (column_id) REFERENCES column_info (id),
    FOREIGN KEY (metric_id) REFERENCES metric_info (id)
) ENGINE=InnoDB COMMENT='字段与指标的多对多关系；联合主键避免重复关系';
"""


def render_model_doc() -> str:
    lines = ["# 简化销售经管数仓设计", "", "依据：根目录 index.html 的 fields2026/fieldsGoal/fieldsPPL、历史示例问题和 genAiReply。",
             "", "模型包含五张维度表、四张事实表；合同事件和风险快照分开，避免快照重复统计签约额。",
             "收入与销量采用月度粒度；原型的 1月…12月宽表列转换成日期维度，不重复存季度/全年汇总。",
             "产品线、省份/城市/大区、客户名称分别并入产品、经营单元、项目维度，减少维表数量。",
             "", "## 示例问题与数据来源", "", "| 示例 | 来源 |", "| --- | --- |",
             "| 产品线销售、北京产品线收入、深圳产品销售、产品型号排名 | fact_sales_monthly + dim_date/business_unit/product |",
             "| 政企收入范围筛选及行业占比 | fact_sales_monthly + dim_industry，聚合后 HAVING |",
             "| 各经营单元收入与完成率 | 收入先按年/单元汇总，再关联 fact_target_yearly |",
             "| 商业目标与商解目标 TOP5 | fact_target_yearly + dim_business_unit |",
             "| 产品线/经营单元同比趋势 | fact_sales_monthly 同维度同期间跨年比较 |",
             "| 每月合同金额趋势 | fact_contract_line + dim_date，通过 signed_date_id |",
             "| 当前高风险项目数量、明细 | fact_project_snapshot 每项目最新有效快照 + dim_project |", "",
             "## 关联结构", "", "```mermaid", "erDiagram",
             "    dim_date ||--o{ fact_sales_monthly : month_date_id",
             "    dim_business_unit ||--o{ fact_sales_monthly : business_unit_id",
             "    dim_product ||--o{ fact_sales_monthly : product_id",
             "    dim_industry ||--o{ fact_sales_monthly : industry_id",
             "    dim_business_unit ||--o{ fact_target_yearly : business_unit_id",
             "    dim_date ||--o{ fact_contract_line : signed_date_id",
             "    dim_project ||--o{ fact_contract_line : project_id",
             "    dim_business_unit ||--o{ fact_contract_line : business_unit_id",
             "    dim_product ||--o{ fact_contract_line : product_id",
             "    dim_industry ||--o{ fact_contract_line : industry_id",
             "    dim_date ||--o{ fact_project_snapshot : snapshot_date_id",
             "    dim_project ||--o{ fact_project_snapshot : project_id",
             "    dim_business_unit ||--o{ fact_project_snapshot : business_unit_id",
             "    dim_industry ||--o{ fact_project_snapshot : industry_id", "```", "",
             "年度目标只按 target_year 与汇总收入的年份匹配，不建立到日期维度某一天的外键。",
             "事实表共享维度；多个事实表先各自聚合到共同粒度，再关联，避免明细相乘。", "",
             "## 表、字段与主外键", ""]
    for table in TABLES:
        lines.extend([f"### {table.name}（{'维度表' if table.role == 'dim' else '事实表'}）", "",
                      f"粒度：{table.grain}。主键：`{', '.join(table.primary_key)}`。", "", table.description, "",
                      "| 字段 | 类型 | 键/角色 | 含义 |", "| --- | --- | --- | --- |"])
        for column in table.columns:
            roles = ["PK"] if column.name in table.primary_key else []
            if column.reference:
                roles.append("FK → " + ".".join(column.reference))
            lines.append(f"| {column.name} | {column.sql_type} | {'；'.join(roles) or column.role} | {column.description} |")
        lines.append("")
        if table.constraints:
            lines.extend(["其他约束：" + "；".join(f"`{constraint}`" for constraint in table.constraints) + "。", ""])
    lines.extend(["## 口径与简化假设", "", "- 所有金额为不含税人民币元，展示万元时除以 10000；使用 DECIMAL(18,2)。",
        "- 原型仅列出商业目标/商解目标名称，未定义其计算口径；本演示将商业目标解释为合同签约额目标，商解目标解释为商业解决方案收入目标，实际业务需确认。",
        "- 原型没有明确总收入目标，新增 revenue_target_amount，并与前两类目标分开；这是明确的 demo 假设。",
        "- 月度销量也是合成演示度量，不能把源表合同台套数直接复制到每月；实际接入需按销售发生月份分配。",
        "- 北京/深圳筛选按经营单元驻地城市，不能解释为最终客户所在地；本简化模型不分析客户地址。",
        "- 年度目标没有产品/行业粒度，也不按月重复存储。完成率分母为全年目标；合并单元先求总金额再求比例。",
        "- 同比默认比较 2026/2025 年 1-5 月；对未发生月份返回无数据，不能把未来日期维度当成收入事实。",
        "- 当前风险以每个项目最近快照为准，再排除已完成项目；历史高风险不能直接累加。",
        "- 合同按明细金额累加，合同数量去重；风险快照中不再重复存合同金额。",
        "- 简化样例不含税额、成本、预算、应收账款账龄和完整回款流水，相关残留示例需后续扩展，不凭空回答。",
        "- 数据截至 2026-05-31；目标 TOP5、月度签约额和 7 个当前高风险项目与选定演示一致，其余为确定性合成数据。原型中的错误合计与百分比不照搬。", "",
        "## meta 与现有构建流程", "", "meta.sql 创建四张元数据表，不存实际销售事实，也不复制九张业务表。",
        "table_info.id=DW 表名；column_info.id=表名.字段名，table_id 外键指向 table_info；metric_info.id=指标名；",
        "column_metric 使用 (column_id,metric_id) 联合主键，分别外键指向字段和指标。",
        "", "| 元数据表 | 主键 | 外键 | 全部字段 |", "| --- | --- | --- | --- |",
        "| table_info | id | 无 | id、name、role、description |",
        "| column_info | id | table_id → table_info.id | id、name、type、role、examples、description、alias、table_id |",
        "| metric_info | id | 无 | id、name、description、relevant_columns、alias |",
        "| column_metric | (column_id, metric_id) | column_id → column_info.id；metric_id → metric_info.id | column_id、metric_id |", "",
        "conf/meta_config.yaml 描述全部字段、别名、关联和指标。metadata-init 从 DW 读取实际类型/示例，再构建 meta、Qdrant 和 ES。",
        "SQL 只创建 metadata 的空表；避免 SQL 预填元数据与现有构建脚本重复插入。", "",
        "## 验证与使用", "", "参考 SQL 见 database/reference_queries.sql；运行 python -m pytest tests/test_warehouse.py。",
        "验证使用 SQLite 内存库检查同一份 SQL 文件中的关系/样例及参考查询；MySQL 方言和容器初始化仍需实际 MySQL 8 验证。",
        "Docker 已有数据卷时不会重新执行初始化 SQL，现有库需独立迁移；这些文件用于新的空数据卷，不自动删除既有数据。", "",
        "重新生成：python -m app.scripts.generate_demo_warehouse。该命令覆盖 dw.sql、meta.sql、meta_config.yaml 和本说明，不连接数据库。"])
    return "\n".join(lines) + "\n"


def main() -> None:
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docker/mysql/dw.sql").write_text(render_dw(), encoding="utf-8")
    (ROOT / "docker/mysql/meta.sql").write_text(render_meta_sql(), encoding="utf-8")
    (ROOT / "conf/meta_config.yaml").write_text(render_meta_config(), encoding="utf-8")
    (ROOT / "docs/warehouse-model.md").write_text(render_model_doc(), encoding="utf-8")
    print("Generated dw.sql, meta.sql, meta_config.yaml and warehouse-model.md")


if __name__ == "__main__":
    main()
