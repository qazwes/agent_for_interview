# 测试与验收说明

测试脚本统一放在本目录。除明确说明外，所有命令从 **`my-agent/` 目录**执行。代码阅读顺序见 [项目 README](../README.md#代码阅读指引)，业务分层和接口见 [重构说明](../docs/frontend-reconstruction.md)。

## 1. 测试分类与执行顺序

| 顺序 | 测试入口 | 环境要求 | 真实聊天模型 | 数据影响 |
| --- | --- | --- | --- | --- |
| 1 | `python -m pytest tests -q` | Python 开发依赖，或独立测试镜像 | 不调用 | 内存 SQLite，不连接部署数据库 |
| 2 | `python -m app.scripts.verify_meta_knowledge` | MySQL、Qdrant、ES、Embedding 和已构建知识库 | 不调用；会调用 Embedding | 读取数据和索引，不重建 |
| 3 | `python tests/smoke_api.py` | web、api、应用库 | 不调用 | 创建并清理自己的测试会话和收藏 |
| 4 | `node tests/browser_smoke.mjs` | 产品服务、前端依赖、Chrome/Chromium | 不调用，SSE 模拟 | 创建测试会话和收藏，详见第 5 节 |
| 4b | `node tests/browser_query_failure.mjs` | 已构建前端、前端依赖、Chrome/Chromium | 不调用，全部 API 模拟 | 不写产品数据库 |
| 5 | `python tests/smoke_api.py --query "问题"` | 完整服务、知识库、有效模型配置 | **调用** | 保留真实问数会话与已处理反馈 |

前端变更另需在 `frontend/` 做类型检查和构建，见第 7 节。只改文档时检查链接和命令即可；普通界面修改通常不必重复付费问数。

`pytest tests` 只收集 `test_*.py`，**不会自动运行**接口脚本、浏览器脚本或真实知识库验证。

## 2. 离线回归：验证业务规则

### Docker 测试镜像（推荐）

确认 Docker Desktop 使用 Linux 容器且引擎已启动：

```bash
docker version
docker build --target test -f docker/api/Dockerfile -t my-agent-test:local .
docker run --rm my-agent-test:local
```

首次构建需下载基础镜像和 Python 依赖。测试运行不依赖 Compose 服务、真实密钥或数据卷，无需传入 `.env`。默认 CMD 为 `/app/.venv/bin/python -m pytest tests -q`。修改源码、测试或 SQL/YAML 样例后，重新构建镜像，避免测到旧版。

正式 API 镜像使用 `runtime` 阶段，不包含测试文件及开发依赖。

### 本地 Python

项目要求 Python 3.14 或更高版本，安装含开发组的锁定依赖：

```bash
uv sync --frozen
uv run --frozen python -m pytest tests -q
```

已激活正确环境时可用 `python -m pytest tests -q`。Windows 的 `asyncmy` 安装可能需要 C++ 编译工具；失败时优先用 Linux 测试镜像。

`conftest.py` 为缺失配置提供占位值，测试使用临时数据库或模拟依赖，不通过这些值访问真实服务。

### 文件覆盖范围

| 文件 | 验证内容 | 对应代码 |
| --- | --- | --- |
| [test_warehouse.py](test_warehouse.py) | 12 条参考查询、主外键/唯一粒度、最新风险快照、同期间同比、零目标分母、元数据/ORM 一致性、JSON 兼容性 | DW/Meta SQL、参考 SQL、元数据 YAML |
| [test_verify_meta_knowledge.py](test_verify_meta_knowledge.py) | JSON 类型读取、真实定义差异、重复/过期 payload、缺失 collection、召回 ID | 验证脚本、Meta Repository |
| [test_application.py](test_application.py) | 会话/重发归属、进行中删除限制、收藏去重、常问阈值、反馈快照、密钥不回传、中断恢复、旧终态记录进度兼容 | ApplicationService、Repository、应用 ORM |
| [test_result_presenter.py](test_result_presenter.py) | TOP5 真实合计与单位、比例/AVG 不累加、COUNT 分类、CTE 引用、空结果、建议上下文 | result_presenter.py |
| [test_query_integration.py](test_query_integration.py) | 模拟工作流下 SSE、问题传递、结果保存；并行失败时中断其他步骤；取消、客户端断开、无结果结束后的原始落库状态及手动重发 | QueryService、query_progress.py |
| [test_model_service.py](test_model_service.py) | 模拟有正文回复、空回复失败、异常中的密钥不回传 | ModelService |

SQLite 回归不能证明 MySQL 8 的全部方言与并发行为；模拟工作流不能证明真实 SQL 生成正确。模型连接回归使用模拟响应，不访问模型服务，真实链路另行验收。

### 单文件、单场景与输出判定

```bash
uv run --frozen python -m pytest tests/test_application.py -q
uv run --frozen python -m pytest tests/test_result_presenter.py -k top5 -v
uv run --frozen python -m pytest tests/test_query_integration.py -v --tb=short
docker run --rm my-agent-test:local /app/.venv/bin/python -m pytest tests/test_application.py -v --tb=short
```

全部通过输出 `N passed`，退出码为 0。`FAILED` 是断言失败，按测试名定位规则；`ERROR collecting` 通常是依赖/导入/配置问题，测试尚未开始。PowerShell 用 `$LASTEXITCODE`，Linux 用 `echo $?` 查看上一命令退出码。

## 3. 真实知识库验证

按项目 README 完成部署和知识库构建后执行：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml ps
docker compose --env-file .env -f docker/docker-compose.yaml build api
docker compose --env-file .env -f docker/docker-compose.yaml --profile tools run --rm --no-deps metadata-init python -m app.scripts.verify_meta_knowledge
```

最后一条覆盖 `metadata-init` 的默认构建命令，**只验证**。`--no-deps` 不启动依赖，MySQL、Qdrant、ES、Embedding 必须就绪。已有知识库不必重跑构建。

检查 Meta 定义与依赖、Qdrant 维度/point/payload、ES 取值/分词配置和选定召回案例；数量根据当前配置与 DW 推导。逐项 `[PASS]`/`[FAIL]`，全部通过退出码为 0。刚构建后 ES 搜索可能尚未可见，可稍后重试验证。

失败先看具体对象和差异，再查日志，不要直接重建：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml logs --tail=100 mysql elasticsearch qdrant embedding
```

通过说明定义和基础召回通过，不代表所有问数正确。`test_verify_meta_knowledge.py` 是验证器自身的离线回归，与本节不同。

## 4. 产品接口验收

要求 web/api 正常运行，MySQL 已有 `agent_app`。旧数据卷未建应用库时，先按项目 README 执行 `docker/upgrade-app.ps1` 或 `docker/upgrade-app.sh`，无需重建知识库。

脚本只依赖 Python 标准库，默认访问 http://localhost:8080：

```bash
python tests/smoke_api.py
python tests/smoke_api.py --base-url http://localhost:8090
```

也可将地址换为远程 Linux 的 `http://服务器地址:8080`。默认检查健康响应、React 静态资源入口、会话创建/重命名/置顶/读取/删除、收藏、常问结构、模型列表无密钥字段、反馈列表结构；结构检查不等于覆盖全部业务规则。

不调用 LLM。临时会话和唯一收藏在结束时清理；若服务失联导致清理失败，可手动删除“验收测试会话”和“验收问题-…”收藏。

### 在 API 容器内执行

宿主 Python 访问 localhost 有问题时，复制同一脚本。通过 Compose 获取容器 ID，避免固定容器名称。

Windows PowerShell：

```powershell
$testApiContainer = docker compose --env-file .env -f docker/docker-compose.yaml ps -q api
docker cp tests/smoke_api.py "${testApiContainer}:/tmp/smoke_api.py"
docker compose --env-file .env -f docker/docker-compose.yaml exec -T api python /tmp/smoke_api.py --base-url http://web
```

Linux：

```bash
test_api_container=$(docker compose --env-file .env -f docker/docker-compose.yaml ps -q api)
docker cp tests/smoke_api.py "$test_api_container:/tmp/smoke_api.py"
docker compose --env-file .env -f docker/docker-compose.yaml exec -T api python /tmp/smoke_api.py --base-url http://web
```

`http://web` 走内部 80 端口，不受宿主 `WEB_PORT` 影响。改脚本后重新复制。成功逐项输出 `[PASS]`，最后 `All checks passed.`，退出码 0；断言/HTTP 错误返回非零退出码。

## 5. 浏览器交互验收

从 `my-agent/frontend/` 安装依赖：

```bash
corepack pnpm install --frozen-lockfile
```

脚本优先使用 Windows 常见路径的 Chrome。没有该浏览器时，从 `frontend/` 安装 Chromium：

```bash
corepack pnpm exec playwright install chromium
```

Linux 缺系统依赖时，在有安装权限的环境运行 `corepack pnpm exec playwright install --with-deps chromium`。脚本需要 Node.js，不能用 API 容器里的 Python 执行。

返回 `my-agent/`，确认 Docker 页面可打开：

```bash
node tests/browser_smoke.mjs
```

非默认地址或指定浏览器路径，Windows PowerShell：

```powershell
$env:TEST_BASE_URL = 'http://localhost:8090'
$env:BROWSER_EXECUTABLE = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
node tests/browser_smoke.mjs
```

Linux：

```bash
TEST_BASE_URL=http://localhost:8090 BROWSER_EXECUTABLE=/usr/bin/chromium node tests/browser_smoke.mjs
```

`BROWSER_EXECUTABLE` 可省略，使用默认检测或 Playwright 浏览器。测试无界面运行。

验证开场白保存/刷新、真实会话创建/重命名/置顶、模拟 SSE 展示、TOP5 统计、图表、真实收藏、编辑取消、模型页面/新增弹窗、反馈搜索、移动端溢出、页面异常。

**问数 SSE 是模拟的，不执行 SQL，不保存模拟消息到服务器。** 会话、收藏、模型列表、反馈列表走真实 API；显示配置存在隔离测试浏览器的 `localStorage`。不覆盖真实模型连接、切换后的问数和反馈提交/处理全流程，需下一节和人工验收补充。

成功输出各组 `[PASS]`，退出码 0。截图写入被版本控制忽略的 `tests/artifacts/`：

| 截图 | 用途 |
| --- | --- |
| `welcome.png` | 桌面欢迎页 |
| `answer.png` | 表格、统计、图表与分析过程 |
| `feedbacks.png` | 回复校对搜索页 |
| `mobile.png` | 390 × 844 视口 |

截图供人工对照原型，无逐像素比较。结束清理自己的会话；收藏在成功检查后删除，异常可能残留“浏览器验收会话”或“浏览器验收：…”收藏，可手动清理。

### 查询失败状态专项回归

使用相同的 Node/浏览器环境，从 `my-agent/` 运行：

```bash
node tests/browser_query_failure.mjs
```

同样支持 `TEST_BASE_URL` 和 `BROWSER_EXECUTABLE`。脚本加载部署后的真实前端，但所有产品 API、SSE 和历史数据均模拟，不调用模型、不写数据库。验证以下行为：

- 表过滤和指标过滤同时运行，指标过滤报错后表过滤显示“已中断”；成功步骤和失败步骤保留原状态。
- 服务端发送错误后故意不关闭连接，前端仍立即停止读流、恢复操作；错误之后的迟到进度/结果不能覆盖终态。
- 刷新恢复旧版错误记录时，不再出现遗留的转圈状态。
- 手动重发追加消息并保留旧问答。
- 没有结果的异常断流和主动停止，都结束尚在运行的步骤。

成功输出五组 `[PASS]`，退出码为 0。普通浏览器验收检查成功路径，本脚本检查故障路径，两者应一起运行。

## 6. 真实问数与人工核对

前提：知识库通过、产品接口可用，当前模型地址、ID、密钥有效。**调用真实模型，可能产生费用。**

```bash
python tests/smoke_api.py --query "查询2026年商业目标最高的五个经营单元，同时展示商解目标，金额单位为万元。"
```

或在已复制脚本的 API 容器内：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml exec -T api python /tmp/smoke_api.py --base-url http://web --query "查询2026年商业目标最高的五个经营单元，同时展示商解目标，金额单位为万元。"
```

先检查普通接口，再消费 SSE，检查有结果/SQL 展示、保存与返回的数据一致，对真实回答创建反馈并标记已处理。真实会话和反馈保留供界面核对。

脚本验证链路及保存一致，**不自动判断任意问题的业务答案是否正确**。上述演示问句应人工核对：

| 经营单元 | 商业目标（万元） | 商解目标（万元） |
| --- | ---: | ---: |
| 北京代表处 | 7,950 | 1,200 |
| 上海代表处 | 7,070 | 980 |
| 浙江代表处 | 6,460 | 860 |
| 江苏代表处 | 5,560 | 720 |
| 山东代表处 | 4,090 | 650 |
| 返回五条合计 | **31,130** | **4,410** |

值针对当前演示数据，改样例后同步参考结果。其他问题对照 [参考 SQL](../database/reference_queries.sql) 和 [数仓设计](../docs/warehouse-model.md)，注意时间范围、目标分母、最新风险快照和金额换算。

人工路径：新建 → 提问 → 展开实际 SQL → 核对表格/统计/图表 → 刷新恢复 → 收藏 → 编辑重发 → 提交反馈 → 回复校对筛选/处理。重发应追加并保留旧记录；进行中删除应被拒绝；停止后消息应结束流式状态。

## 7. 前端类型检查与构建

从 `frontend/` 执行：

```bash
corepack pnpm lint
corepack pnpm build
```

`lint` 当前是 TypeScript 类型检查，同时启用 `noUnusedLocals` 和 `noUnusedParameters` 检测未使用的导入、局部变量和参数；`build` 先类型检查再 Vite 构建。通过不代表交互验收通过。包体积提示不等于构建失败，以退出码及产物判断。

## 8. 常见失败排查

| 现象 | 优先检查 |
| --- | --- |
| Docker 无法连接引擎 | 启动 Desktop/Linux Engine，确认 Linux 容器；`docker version` 查看 Server |
| pytest 收集失败/模块缺失 | 工作目录、Python 版本、开发依赖；用测试镜像复现 |
| 改完结果没变化 | 是否重建测试/API/web 镜像或重复制容器内脚本 |
| 连接失败/502 | web/api 就绪情况、`WEB_PORT`、API 日志 |
| 应用表缺失/无权限 | 旧卷是否升级，`db_app` 与容器配置是否一致 |
| 知识库定义/point/payload/召回失败 | 按报告定位对象，核对 YAML、Meta、索引，再决定迁移或重建 |
| HTTP 200 但没结果 | SSE 是否有 `type: error`；200 仅表示流式连接建立，查失败阶段 |
| 模型 429/鉴权失败/空正文 | 模型服务限流、配额、密钥、接口前缀和 ID；无需重建知识库 |
| 浏览器不存在 | 安装 Chromium 或指定有效 `BROWSER_EXECUTABLE` |
| 浏览器测试超时 | 页面版本、服务就绪、异常定位器/接口及截图 |

实时观察后端日志：

```bash
docker compose --env-file .env -f docker/docker-compose.yaml logs -f --tail=100 api
```

`Ctrl+C` 只退出日志跟随，不停容器。不要删除数据卷解决测试失败。保留测试名、失败阶段和必要日志，不粘贴 `.env` 或密钥。

## 9. 新功能如何补测试

业务规则放入相应 `test_*.py`：准备最小输入/临时数据 → 调用业务函数 → 断言结果或异常。模型/检索依赖模拟，持久化规则用临时 SQLite，再补真实接口验收。

例如常问阈值验证“等于不出现、超过才出现”；统计验证真实合计和比例不累加。测试应验证行为，避免只重复实现步骤。接口扩展 `smoke_api.py`，交互扩展 `browser_smoke.mjs`，同步本文覆盖范围。
