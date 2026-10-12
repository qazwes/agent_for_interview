"""
MySQL 客户端管理器

统一创建和管理项目中的异步 MySQL 客户端，分别连接结构化元数据 meta、
销售经管数仓 dw 和产品记录 agent_app 三个数据库
模块对外提供可复用的客户端管理器和 session 工厂
方便脚本入口 服务层和仓储层按统一方式访问数据库
"""

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)

from app.conf.app_config import DBConfig, app_config


class MySQLClientManager:
    """管理 MySQL Engine 和 Session 工厂"""

    def __init__(self, config: DBConfig):
        # Engine 是数据库连接层核心对象，底层会维护连接池
        self.engine: AsyncEngine | None = None
        # session_factory 用来按需创建新的 AsyncSession
        self.session_factory = None
        # 保存数据库配置，后面拼接连接地址要用
        self.config = config

    def _get_url(self) -> URL:
        """
        拼接 MySQL 异步连接地址
        mysql+asyncmy 表示：连接 MySQL，并使用 asyncmy 作为异步驱动
        """
        return URL.create(
            "mysql+asyncmy",
            username=self.config.user,
            password=self.config.password,
            host=self.config.host,
            port=self.config.port,
            database=self.config.database,
            query={"charset": "utf8mb4"},
        )

    def init(self):
        """初始化 Engine 和 Session 工厂"""
        # 创建异步 Engine，相当于先把“数据库连接能力”准备好
        self.engine = create_async_engine(
            self._get_url(), pool_size=10, pool_pre_ping=True
        )
        # 基于 Engine 创建 Session 工厂，后面真正查库时再拿 session
        self.session_factory = async_sessionmaker(
            self.engine, autoflush=True, expire_on_commit=False
        )

    async def close(self):
        """释放连接池资源"""
        await self.engine.dispose()


# 分别连接元数据库、数仓和应用数据库
# 后续由不同 repository 按职责分别使用
meta_mysql_client_manager = MySQLClientManager(app_config.db_meta)
dw_mysql_client_manager = MySQLClientManager(app_config.db_dw)
app_mysql_client_manager = MySQLClientManager(app_config.db_app)
