# my-agent：AI 问数应用

my-agent 是面向销售经营分析的自然语言问数应用。用户输入问题后，系统检索字段、指标和字段取值，生成并执行 SQL，以表格、统计和图表呈现结果。

项目使用 React、TypeScript、FastAPI 和 LangGraph，通过 Docker Compose 部署前后端、MySQL、Elasticsearch、Qdrant 和 Embedding 服务，支持 Windows 开发与 Linux 部署。另保留独立语音识别的部署配置，暂未接入产品。

首次部署从[快速部署](#快速部署)开始；了解实现从[代码阅读指引](#代码阅读指引)开始；测试方法统一见 [tests/README.md](tests/README.md)。

## 功能

| 页面 | 功能 |
| --- | --- |
| 智能问数 | 自然语言提问、流式进度、SQL 展示、表格/统计/图表、会话历史、置顶/重命名/删除、收藏、编辑重发、停止查询、回答反馈 |
| 应用配置 | 开场白、开场问题、下一步建议开关、常问开关与阈值、模型配置入口开关 |
| 模型配置 | 新增 OpenAI 兼容模型配置、连接测试、保存当前模型选择 |
| 回复校对 | 查看回答快照、搜索、状态筛选、分页、处理状态和备注 |

查询失败时，失败节点显示错误，其他未完成步骤显示“已中断”；用户可手动重新发送问题，旧问答记录保留。主动停止和异常断流同样结束进度状态。

开场白等显示设置保存在浏览器 `localStorage`；会话、收藏、反馈和模型配置保存在应用数据库。常问根据已保存的用户问题统计，次数严格超过阈值才展示；下一步建议由规则生成。

## 目录与架构

```text
my-agent/
├── app/
│   ├── agent/                  # LangGraph 工作流、节点、State、Context
│   ├── api/                    # Router、请求 Schema、依赖组装、生命周期
│   ├── clients/                # 数据库、检索和 Embedding 客户端管理
│   ├── conf/                   # 配置对象
│   ├── entities/               # 元数据业务实体
│   ├── models/                 # SQLAlchemy ORM
│   ├── repositories/           # MySQL、Qdrant、ES 读写
│   ├── scripts/                # 构建、验证、数仓生成与启动检查
│   └── services/               # 查询、知识库、产品业务与结果整理
├── conf/                       # 基础设施配置、业务元数据定义
├── prompts/                    # 检索、SQL 生成和修正提示词
├── frontend/                   # React 页面、组件、Hook、HTTP 客户端
├── docker/                     # Compose、镜像构建、Nginx、SQL 初始化
├── database/                   # 演示问句的校验 SQL
├── tests/                      # 回归与验收脚本，详见其中的 README.md
├── docs/                       # 数仓设计及实现说明
├── main.py                     # FastAPI 应用入口
├── pyproject.toml / uv.lock     # Python 依赖与锁文件
├── .env.example                # 环境变量示例
└── LICENSE
```

后端按 **Router / Schema → Service → Repository → ClientManager** 分层。Router 接收请求和返回响应，Service 组织业务规则及事务，Repository 执行读写，ClientManager 管理连接。问数由 Service 调用 LangGraph 编排。

| 服务 | 用途 | 访问方式 |
| --- | --- | --- |
| web | Nginx 静态页面及 API/SSE 代理 | 默认 http://localhost:8080 |
| api | FastAPI、LangGraph | 经 web 访问，不单独映射端口 |
| mysql | 数仓、元数据库、应用数据库 | Compose 内部网络 |
| adminer | 浏览器查看和管理 MySQL 数据 | 默认 http://localhost:8081，仅本机 |
| elasticsearch | 字段取值全文检索、IK 中文分词 | Compose 内部网络 |
| kibana | ES 索引查看与检索调试 | 默认 http://localhost:5601，仅本机 |
| qdrant | 字段与指标向量检索 | Compose 内部网络 |
| embedding | TEI、bge-large-zh-v1.5、CPU | Compose 内部网络 |
| asr | 预留 FunASR CPU 语音识别服务，默认不启动 | speech profile，无宿主端口，未接入 api |
| asr-model-download | 从 Hugging Face 下载三个语音模型 | tools 工具服务，手动运行 |
| model-download | 下载 Embedding 模型到持久化卷 | tools 工具服务，手动运行 |
| metadata-init | 构建结构化元数据和检索索引 | tools 工具服务，手动运行 |

容器间通过 `mysql:3306`、`embedding:80` 等服务名访问。容器里的 `localhost` 表示当前容器。

## 数据库

同一个 MySQL 容器运行三个数据库，连接分别在 [app_config.yaml](conf/app_config.yaml) 的 `db_dw`、`db_meta`、`db_app` 中配置。

| 数据库 | 内容 | 初始化文件 |
| --- | --- | --- |
| dw | 日期、经营单元、产品、行业、项目五张维度表；月度收入/销量、年度目标、合同明细、项目风险快照四张事实表 | [dw.sql](docker/mysql/dw.sql) |
| meta | 表、字段、指标及字段指标依赖关系 | [meta.sql](docker/mysql/meta.sql) |
| agent_app | 会话、消息、收藏、反馈、模型配置和应用设置六张表 | [agent_app.sql](docker/mysql/agent_app.sql) |

演示数据截至 **2026-05-31**，采用确定性合成数据。金额按不含税人民币元存储，展示为万元时除以 10000。商业目标表示签约额目标，商解目标表示商解收入目标；总收入目标用于收入完成率计算。完整字段、主外键、粒度和口径见 [数仓设计](docs/warehouse-model.md)，12 条演示查询见 [reference_queries.sql](database/reference_queries.sql)。

## 快速部署

需要 Docker Engine 或 Docker Desktop（Linux 容器）和 Docker Compose v2。Embedding 镜像使用 `linux/amd64`，建议部署到同架构 Linux 主机。首次构建和下载需要访问镜像源、Python/Node 包源及模型站点。

除特别说明外，以下命令从 **`my-agent/` 目录**执行。

### 1. 创建配置

Linux：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

编辑 `.env`：

- 设置 `MYSQL_ROOT_PASSWORD`、`MYSQL_PASSWORD`、`DW_QUERY_PASSWORD`。只读账号初始化要求 `DW_QUERY_PASSWORD` 仅包含字母、数字、下划线和连字符。
- 设置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`，三者必须对应同一个可用的 OpenAI 兼容模型服务。Base URL 填写接口前缀，例如 `https://服务域名/v1`。
- `WEB_PORT` 默认 8080，`KIBANA_PORT` 默认 5601，`ADMINER_PORT` 默认 8081；端口冲突时修改。
- 按需设置 `HF_ENDPOINT`、`HF_TOKEN`、`EMBEDDING_REVISION`。

`.env` 不进入版本控制或镜像。Compose 将配置注入容器环境变量；默认 Meta 和应用库使用 `HeJing`，共用 `MYSQL_PASSWORD`，数仓查询使用单独的只读账号 `dw_reader`。

### 2. 检查并构建

```bash
docker compose --env-file .env -f docker/docker-compose.yaml config --quiet
docker compose --env-file .env -f docker/docker-compose.yaml build api web elasticsearch
```

Python 和前端分别使用 `uv.lock`、`frontend/pnpm-lock.yaml` 安装锁定依赖。

### 3. 下载 Embedding 模型

```bash
docker compose --env-file .env -f docker/docker-compose.yaml --profile tools run --rm --no-deps model-download
```

模型写入 `embedding_models` 命名卷，TEI 从同一卷只读加载。该步骤不调用聊天模型，也不依赖数据库。

语音模型使用单独的数据卷；当前暂未接入产品，资源充足后按下方[部署预留](#语音识别部署预留)独立验证。

### 4. 启动依赖并构建知识库

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d mysql adminer elasticsearch kibana qdrant embedding
docker compose --env-file .env -f docker/docker-compose.yaml --profile tools run --rm metadata-init
```

MySQL 在**首次初始化空数据卷**时执行 `docker/mysql/` 中的 SQL 和 shell 脚本：创建三个数据库、插入数仓样例、授予应用账号权限，并创建仅有 DW SELECT 权限的 `dw_reader`。

`metadata-init` 从 [meta_config.yaml](conf/meta_config.yaml) 和数仓读取定义及样例，构建 Meta、Qdrant 向量和 ES 取值索引。**构建命令用于首次空库初始化，目前不支持安全地重复构建已有知识库。** 已有环境日常启动无需执行它。

### 5. 验证知识库并启动应用

```bash
docker compose --env-file .env -f docker/docker-compose.yaml --profile tools run --rm --no-deps metadata-init python -m app.scripts.verify_meta_knowledge
docker compose --env-file .env -f docker/docker-compose.yaml up -d api web
docker compose --env-file .env -f docker/docker-compose.yaml ps
```

验证命令覆盖工具服务的默认命令，实际只验证、不构建。它读取 MySQL/Qdrant/ES 并调用 Embedding，不调用聊天模型。每项输出 `[PASS]` 或 `[FAIL]`，全部通过时退出码为 0；失败排查见 [测试说明](tests/README.md)。

打开 http://localhost:8080，API 文档为 http://localhost:8080/docs。可尝试：

> 查询2026年商业目标最高的五个经营单元，同时展示商解目标，金额单位为万元。

当前样例返回五个经营单元，商业目标合计 **31,130 万元**、商解目标合计 **4,410 万元**。这些合计仅表示返回的五条记录。

`/health` 仅检查 API 进程响应；模型鉴权和完整问数通过真实查询验收。

## 运维与开发

### 更新应用与查看日志

```bash
# 修改代码后构建并更新前后端。
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build --no-deps api web

# 实时查看后端日志，Ctrl+C 退出跟随。
docker compose --env-file .env -f docker/docker-compose.yaml logs -f --tail=100 api

# 查看依赖状态与日志。
docker compose --env-file .env -f docker/docker-compose.yaml ps
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=100 mysql elasticsearch qdrant embedding

# 停止服务并保留数据卷。
docker compose --env-file .env -f docker/docker-compose.yaml down
```

修改 `.env` 后，用 `up -d --no-deps api` 重新创建后端以加载环境变量；仅 `restart` 不会更新环境变量。已有 MySQL 数据卷不会因修改初始化 SQL 或密码配置而重新初始化；结构和密码变更需要执行相应数据库迁移或账号更新。

### 将已有数据库账号迁移为 HeJing

新环境会自动创建 `HeJing`。已有数据卷使用旧账号时，从 `my-agent/` 目录执行一次迁移，再更新服务：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml cp docker/migrations/add-hejing-user.sh mysql:/tmp/add-hejing-user.sh
docker compose --env-file .env -f docker/docker-compose.yaml exec -T mysql sh /tmp/add-hejing-user.sh
docker compose --env-file .env -f docker/docker-compose.yaml up -d --no-deps mysql
docker compose --env-file .env -f docker/docker-compose.yaml up -d --build --no-deps api
```

迁移脚本为新账号复制旧账号的认证信息，授予 DW 查询权限和 Meta、应用库的数据读写权限；保留旧账号和全部数据，不输出密码或认证哈希。若 `HeJing` 已存在，保留其已有密码。Adminer 用 `HeJing` 和原来的 `MYSQL_PASSWORD` 登录。仅修改 Compose 的 `MYSQL_USER` 不会更新已有数据库账号。

### 为已有数据卷创建应用库

MySQL 已有数据卷且缺少 `agent_app` 时，确认 MySQL 服务运行后执行：

Windows PowerShell：

```powershell
powershell -File docker/upgrade-app.ps1
```

Linux：

```bash
sh docker/upgrade-app.sh
```

脚本幂等创建应用库与表并授予权限，不清空会话，不重建 DW、Meta 或索引。随后按上面的更新命令启动前后端。

### 语音识别部署预留

**当前仅保留独立 ASR 的部署配置和模型文件，尚未接入产品功能。** 主后端没有注册 `/api/speech/transcribe`，前端不显示麦克风按钮或可用的语音开关。

本机验证环境为约 16 GB 宿主内存、约 8 GB Docker 内存，同时运行问数依赖。语音模型加载期间，宿主可用内存降到约 1.2 GB，Docker 容器查询曾返回 500，ASR 多次重新启动且未通过健康检查。停止 ASR 后，现有页面恢复。当前证据表明存在明显资源压力，但容器最终状态未标记 `OOMKilled`，不能仅凭退出码 137 确认是 OOM。**模型下载成功；模型加载和真实转写尚未验证成功。**

保留的内容：

- [Dockerfile](docker/asr/Dockerfile)：Python 3.11、CPU 版 PyTorch、FunASR 和 FFmpeg，独立于主后端环境。
- [download_models.py](docker/asr/download_models.py)：从 Hugging Face 下载 `funasr/paraformer-zh`、`funasr/fsmn-vad`、`funasr/ct-punc`。
- [server.py](docker/asr/server.py)：独立服务的加载、音频解码、时长限制和识别处理，供后续验证与接入。
- Compose 的 `asr`、`asr-model-download` 服务及 `asr_models` 卷。
- `.env.example` 的 `ASR_CPU_THREADS`、三个模型 revision；下载沿用 `HF_ENDPOINT`、`HF_TOKEN`。

下载的三个模型权重文件约为 840 MiB、2 MiB、1073 MiB；这些是文件大小，**不代表加载或推理内存上限**。加载时还会占用模型对象、权重副本、运行时及其他容器所需内存。

`asr` 放在 `speech` profile，默认 `docker compose up -d` 不启动；关闭自动重启，避免失败后反复加载。无需修改主应用配置或数据库。未来在资源充足的 Linux 环境中，先独立验证：

```bash
# 下载模型，已下载的文件会复用；可单独执行，不启动推理。
docker compose --env-file .env -f docker/docker-compose.yaml --profile tools run --rm --build --no-deps asr-model-download

# 显式启动 ASR，仅在准备好资源后执行。
docker compose --env-file .env -f docker/docker-compose.yaml --profile speech up -d asr
docker compose --env-file .env -f docker/docker-compose.yaml --profile speech ps asr
docker compose --env-file .env -f docker/docker-compose.yaml --profile speech logs --tail=100 asr

# 加载失败或资源紧张时停止，保留模型卷。
docker compose --env-file .env -f docker/docker-compose.yaml --profile speech stop asr
```

推理容器只读加载本地模型，音频在内存临时目录处理并清理，不保存到数据库或模型卷。服务没有映射宿主端口；内部 `POST /transcribe` 仅供独立测试，不是产品 API。等待日志显示 `ASR models ready`、容器 healthy 后，按[独立 ASR 测试说明](tests/README.md#10-独立-asr-预留服务验证)检查真实音频。

后续接入顺序：先验证资源和中文业务录音效果，再补主后端 Router → Service → ASR Client、Nginx 上传配置、前端录音/回填及应用开关。届时采用录完转写、用户编辑确认后发送；远程浏览器录音需 HTTPS。当前不宣称语音输入已经可用。

### Adminer 查看和管理 MySQL

已有环境从 `my-agent/` 目录执行以下命令添加服务，无需重建后端或初始化数据库：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml up -d adminer
docker compose --env-file .env -f docker/docker-compose.yaml ps adminer
```

默认打开 http://localhost:8081，登录填写：

| 登录项 | 填写内容 |
| --- | --- |
| 系统 / System | MySQL |
| 服务器 / Server | `mysql`（容器服务名） |
| 用户名 / Username | `HeJing` |
| 密码 / Password | `.env` 中的 `MYSQL_PASSWORD` |
| 数据库 / Database | `agent_app` |

登录后可以通过浏览器处理数据：

1. **查看表结构**：点击 `chat_session` 或 `chat_message` 表名，查看字段、主键和索引。
2. **查看记录**：点击“选择数据 / Select data”，查看行；使用筛选条件和排序定位数据。
3. **查看某个会话**：在 `chat_session` 找到 `id`，在 `chat_message` 的筛选中设置 `session_id = 该ID`，按 `created_at` 排序。`content` 是消息正文，`payload` 包含结果、SQL 和分析步骤。
4. **编辑记录**：点击行旁的“编辑 / Edit”，例如修改会话 `title`，保存后刷新问数页面即可看到变化。
5. **执行查询**：进入“SQL 命令 / SQL command”，执行下面的 SQL。
6. **导出数据**：使用“导出 / Export”选择 SQL 或 CSV；需要修改数据前可以先导出备份。

```sql
SELECT id, title, pinned, created_at, updated_at
FROM chat_session ORDER BY updated_at DESC LIMIT 20;

SELECT id, session_id, role, content, status, payload, created_at
FROM chat_message ORDER BY created_at DESC LIMIT 20;
```

Adminer 的修改直接写入真实数据库，不经过应用的业务规则。会话删除、问题重发和反馈处理优先使用应用页面，避免绕过进行中查询检查等规则；不要清空仍在使用的表或随意修改记录 ID。应用升级通过迁移脚本维护，Adminer 中改表不会同步更新项目 SQL/ORM。

查看元数据时，数据库改为 `meta`，使用同一账号；查看数仓时用 `dw_reader`、`.env` 中的 `DW_QUERY_PASSWORD` 和数据库 `dw`，该账号只能查询。

已有 `.env` 不必添加 `ADMINER_PORT`，默认使用 8081；需要换端口时再设置并重新执行 `up -d adminer`。默认仅监听本机；Linux 远程部署使用 `ssh -L 8081:127.0.0.1:8081 用户名@服务器地址` 建立隧道，然后打开本机地址。

### Kibana 检索调试

访问 http://localhost:5601，在 Management → Dev Tools 中查看取值索引：

```http
GET value_index/_count

GET value_index/_search
{
  "query": { "match": { "value": "北京" } },
  "size": 10
}
```

Kibana 与 ES 使用相同的 8.19.10 版本，仅为调试工具。远程 Linux 部署时可使用 `ssh -L 5601:127.0.0.1:5601 用户名@服务器地址`，再通过本机访问。

### 前端开发

Docker 应用运行后，从 `frontend/` 执行：

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm dev
```

打开 http://localhost:5173。Vite 默认将 `/api` 代理到 http://127.0.0.1:8080；端口有变化时，在 `frontend/.env.local` 设置 `VITE_DEV_PROXY_TARGET`，配置格式见 [frontend/.env.example](frontend/.env.example)。

### 数仓样例维护

在生成器中调整模型或样例后，从项目目录执行：

```bash
python -m app.scripts.generate_demo_warehouse
```

该命令覆盖 `dw.sql`、`meta.sql`、`conf/meta_config.yaml` 和数仓设计文档，不连接数据库，也不迁移已有数据或重建索引。修改后按 [测试说明](tests/README.md) 运行数仓回归。

### Linux 部署

将项目代码部署到 Linux，安装 Docker/Compose，创建该环境自己的 `.env`，按快速部署步骤运行。页面通过 `http://服务器地址:8080` 访问，端口应与 `WEB_PORT` 一致。

命名卷由每台机器的 Docker 独立管理，复制代码不会携带已有数据库、索引或模型缓存；保留已有数据时需另行备份与恢复。

## 代码阅读指引

建议从一条用户操作出发，按 **页面 / Hook → HTTP 客户端 → Router / Schema → Service → Repository → 数据库** 阅读。工作流节点和提示词用于理解自然语言如何转换为 SQL。

| 顺序 | 文件入口 | 阅读重点 |
| --- | --- | --- |
| 1. 页面组装 | [main.tsx](frontend/src/main.tsx)、[App.tsx](frontend/src/App.tsx)、[AppLayout.tsx](frontend/src/components/AppLayout.tsx) | 页面切换、布局；问数页保持挂载以保留 SSE |
| 2. 发送与接收 | [ChatPage.tsx](frontend/src/pages/ChatPage.tsx)、[useChat.ts](frontend/src/hooks/useChat.ts)、[agentApi.ts](frontend/src/lib/agentApi.ts) | 输入、消息状态、会话加载、SSE 解析与终态 |
| 3. 请求入口 | [main.py](main.py)、[query_router.py](app/api/routers/query_router.py)、[query_schema.py](app/api/schemas/query_schema.py)、[dependencies.py](app/api/dependencies.py)、[lifespan.py](app/api/lifespan.py) | 路由注册、字段校验、依赖创建、连接初始化/关闭 |
| 4. 问数工作流 | [query_service.py](app/services/query_service.py)、[graph.py](app/agent/graph.py)、[state.py](app/agent/state.py)、[context.py](app/agent/context.py)、[prompts/](prompts/) | 关键词、三路召回、过滤、上下文、SQL 生成/校验/修正/执行 |
| 5. 结果展示 | [run_sql.py](app/agent/nodes/run_sql.py)、[result_presenter.py](app/services/result_presenter.py)、[AnswerCard.tsx](frontend/src/components/AnswerCard.tsx)、[QueryChart.tsx](frontend/src/components/QueryChart.tsx) | 数据 JSON、字段单位、统计、图表和 SQL 展示 |
| 6. 产品读写 | [productApi.ts](frontend/src/lib/productApi.ts)、[application_router.py](app/api/routers/application_router.py)、[application_schema.py](app/api/schemas/application_schema.py)、[application_service.py](app/services/application_service.py)、[application_repository.py](app/repositories/mysql/application/application_repository.py)、[application.py](app/models/application.py) | 会话、重发、收藏、常问、反馈规则与短事务 |
| 7. 配置与模型 | [preferences.tsx](frontend/src/state/preferences.tsx)、[AppConfigPage.tsx](frontend/src/pages/AppConfigPage.tsx)、[ModelConfigPage.tsx](frontend/src/pages/ModelConfigPage.tsx)、[model_service.py](app/services/model_service.py)、[llm.py](app/agent/llm.py) | 浏览器设置、模型连接测试、服务端保存与请求内模型固定 |
| 8. 知识库 | [app_config.yaml](conf/app_config.yaml)、[meta_config.yaml](conf/meta_config.yaml)、[build_meta_knowledge.py](app/scripts/build_meta_knowledge.py)、[meta_knowledge_service.py](app/services/meta_knowledge_service.py) | 配置、定义补全、结构化元数据、向量和全文索引 |
| 9. 错误收尾 | [query_progress.py](app/services/query_progress.py)、[queryProgress.ts](frontend/src/lib/queryProgress.ts) | 并行失败、停止、断流及历史记录的进度终止 |
| 9b. 语音部署预留 | [Dockerfile](docker/asr/Dockerfile)、[download_models.py](docker/asr/download_models.py)、[server.py](docker/asr/server.py) | 独立模型下载/推理配置，暂未接入产品 |
| 10. 测试 | [tests/README.md](tests/README.md) | 各层回归、部署验收及真实模型验证 |

提问链路：`ChatPage → useChat → streamQuery → /api/query → QueryService → graph → run_sql → result_presenter → SSE result → AnswerCard`。

收藏链路：收藏按钮 → `productApi → application_router → ApplicationService → ApplicationRepository → question_favorite`。先读这两条链路，可以分别理解工作流编排和普通业务读写。

## 测试

**完整测试说明见 [tests/README.md](tests/README.md)**，包含前置条件、Windows/Linux 命令、单文件测试、结果判定、数据清理和失败排查。

按“离线回归 → 知识库验证 → 产品接口 → 正常/故障浏览器验收 → 真实问数”执行。离线和浏览器模拟测试不调用聊天模型；真实问数需显式传入 `--query`。

已通过 35 项离线回归（含独立 ASR 的模拟测试）、全后端与测试 Ruff 检查、前端类型检查和生产构建、接口验收、正常/故障浏览器验收，以及真实知识库验证。真实模型查询已验证商业目标 TOP5 的返回、保存和反馈链路。ASR 的真实模型加载及转写尚未通过验证；测试通过不代表所有自然语言问题的业务答案均正确。

## 当前边界与排查

- 目前不提供语音输入/播放、登录、用户管理、报表、台账、日志管理或数据源选择页面。语音仅保留独立部署配置，真实加载和转写待验证。
- 历史问答以 JSON 保存；尚无专门改写“那上海呢”等省略问句的多轮上下文节点。
- 复杂 SQL 表达式的字段含义和单位需业务核对；排名合计只覆盖返回记录，比例及 AVG/MIN/MAX 不累加。
- SSE 的 HTTP 200 表示连接建立，查询结果以 `result` 为准，失败以 `error` 和节点日志定位。
- 模型 502/429、鉴权失败或空回复应检查服务通道、限流/配额、密钥、Base URL 和模型 ID，无需因此重建知识库。

## 许可证

许可证及版权声明见 [LICENSE](LICENSE)。
