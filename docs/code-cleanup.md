# 冗余代码清理记录

本次按实际入口和引用链检查：前端从 `main.tsx → App.tsx` 出发，包含懒加载图表；后端从 `main.py`、FastAPI 路由/依赖、LangGraph 节点出发；同时检查 Docker 命令、维护脚本、pytest 和浏览器验收入口。

## 已清理内容

| 位置 | 删除或调整 | 判断依据 |
| --- | --- | --- |
| `app/agent/graph.py` | 删除独立调试问数入口及其专用导入、注释掉的打印语句 | 正式入口为 QueryService，测试统一在 tests；旧调试问句也不对应当前原型 |
| `app/agent/llm.py` | 删除独立“你好”请求演示 | 模型连接已有产品接口与回归测试 |
| `app/conf/app_config.py` | 删除独立配置打印演示 | 配置由 API/脚本加载，无需保留打印入口 |
| `app/clients/` 四个管理器 | 删除各自的独立演示及专用导入 | ES 演示写入 my-books，Qdrant 演示写入随机 my_collection，与产品无关；连接和知识库已有统一验证 |
| `ColumnMetricMapper.to_entity`、`MetricInfoMapper.to_entity` | 删除未调用的反向转换方法 | 两个 Mapper 目前只用于元数据构建的 to_model；字段、表的双向转换仍用于查询 |
| `result_presenter.py`、`run_sql.py` | 删除未使用的 table_infos 参数及传参 | 展示实际读取最终 SQL、配置元数据和 metric_infos，参数从未读取 |
| `conf/app_config.yaml` 及对应 dataclass | 删除 embedding.model、es.index_name | Embedding 模型由 Compose/TEI 指定；ValueESRepository 将实际索引名固定为 value_index，旧配置 data_agent 从未生效 |
| `frontend/src/pages/ChatPage.tsx` | 删除没有读操作的输入框 ref | ref 仅被赋值，未参与聚焦或其他行为 |
| `frontend/src/lib/productApi.ts` | 将 request 改为模块私有 | 外部只调用 api 方法，无外部 request 引用 |
| `pyproject.toml`、`uv.lock` | 删除 langchain-deepseek，直接声明 langchain-openai；删除 pre-commit 及其独有依赖；删除指向不存在目录的 workspace 配置 | 实际 provider 是 openai，DeepSeek 模型通过兼容协议调用；项目没有 pre-commit 配置/调用；my-agent 内没有另一个 my-agent 子项目 |
| `frontend/package.json`、`pnpm-lock.yaml` | React Vite 插件归入开发依赖 | 插件只参与开发与构建，不作为页面运行依赖 |
| `frontend/tsconfig.app.json` | 启用 noUnusedLocals、noUnusedParameters | 类型检查同时检测后续遗留的局部变量、导入及参数 |

七处独立演示入口共删除 208 行；依赖锁文件删除 9 个包，保留其他包的锁定版本。没有为减少文件数而合并仍有职责的分层模块。

## 仍然需要的入口

- `app/scripts/build_meta_knowledge.py`：Docker metadata-init 调用，负责首次知识库构建。
- `app/scripts/verify_meta_knowledge.py`：真实知识库验收。
- `app/scripts/wait_for_services.py`：API 和 metadata-init 启动前检查依赖。
- `app/scripts/generate_demo_warehouse.py`：README 提供的数仓维护命令，也是离线测试的数据定义来源。
- `tests/`：pytest 自动发现、接口脚本及两种浏览器脚本分别运行，不能只按 Python import 判断是否使用。
- `prompts/`：按 load_prompt 的名称读取；QueryChart 按动态 import 加载。
- FastAPI 路由和 Pydantic 校验器：通过装饰器注册，不需要显式函数调用。
- ORM、业务实体、Mapper、Repository：分别承担数据映射与读写职责；Qdrant/ES payload 还会读取 dataclass 序列化字段。
- `cryptography`、`greenlet`：MySQL 认证和 SQLAlchemy 异步桥接的运行依赖，不能仅因没有直接 import 就删除。
- 包目录中的 `__init__.py` 和 TypeScript 工程配置：用于模块组织与开发工具。

其余现有业务模块均能找到运行、维护或测试入口。此结论来自静态引用分析和回归验收，不等于证明所有分支都曾在生产环境执行。

## 验证方法

按 [测试说明](../tests/README.md) 执行离线回归、前端构建、普通和故障浏览器验收。依赖和配置清理后还应重建 API 镜像，并运行真实知识库验证；它不调用聊天模型，也不重建索引。

本次清理后已完成：84 个 Python 文件语法检查、28 项离线回归、全后端/测试 Ruff 检查、前端类型检查及 Docker 生产构建、Compose 配置解析、正常/故障浏览器验收，以及真实知识库验证（0 项失败）。API/web 容器已更新，数据库和索引保留；本次没有调用真实聊天模型。
