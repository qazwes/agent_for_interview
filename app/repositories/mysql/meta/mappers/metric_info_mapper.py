"""
MetricInfo 映射器

虽然本章重点是表与字段入库，但指标元数据也沿用同样的分层约定：
先以业务实体表达，再通过 Mapper 转成 ORM 模型
"""

from dataclasses import asdict

from app.entities.metric_info import MetricInfo
from app.models.metric_info import MetricInfoMySQL


class MetricInfoMapper:
    """把 `MetricInfo` 业务实体转换为 `MetricInfoMySQL` 模型"""

    @staticmethod
    def to_model(entity: MetricInfo) -> MetricInfoMySQL:
        """把指标业务实体转换为 ORM 模型"""
        return MetricInfoMySQL(**asdict(entity))
