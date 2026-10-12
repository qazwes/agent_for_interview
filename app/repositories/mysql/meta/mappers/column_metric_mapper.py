"""
ColumnMetric 映射器

负责字段与指标关联关系的实体到模型转换，延续元数据模块统一的 Mapper
分层做法，避免上层直接依赖 ORM 细节
"""

from dataclasses import asdict

from app.entities.column_metric import ColumnMetric
from app.models.column_metric import ColumnMetricMySQL


class ColumnMetricMapper:
    """把 `ColumnMetric` 业务实体转换为 `ColumnMetricMySQL` 模型"""

    @staticmethod
    def to_model(column_metric: ColumnMetric) -> ColumnMetricMySQL:
        """把关联关系业务实体转换为 ORM 模型"""
        return ColumnMetricMySQL(**asdict(column_metric))
