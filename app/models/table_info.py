"""
`table_info` ORM 模型

负责定义元数据库中表元数据表的结构，保存纳入知识库的表名、角色和说明
"""

from sqlalchemy import CheckConstraint, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class TableInfoMySQL(Base):
    """表元数据表对应的 ORM 模型"""

    __tablename__ = "table_info"
    __table_args__ = (
        UniqueConstraint("name", name="uq_meta_table_name"),
        CheckConstraint("role IN ('fact', 'dim')"),
    )

    # id 直接使用表名
    # 它既是主键 也是后续字段归属关系里的表标识
    id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="表编号")
    name: Mapped[str] = mapped_column(String(128), comment="表名称")
    role: Mapped[str] = mapped_column(String(32), comment="表类型(fact/dim)")
    description: Mapped[str] = mapped_column(Text, comment="表描述")
