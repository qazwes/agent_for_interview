-- 元数据空表初始化；业务定义来自 conf/meta_config.yaml。
-- metadata-init 从 DW 获取实际字段类型/示例后填充，避免重复预填。
SET NAMES utf8mb4;
CREATE DATABASE IF NOT EXISTS meta DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT SELECT, INSERT, UPDATE, DELETE ON meta.* TO 'didilili'@'%';
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
