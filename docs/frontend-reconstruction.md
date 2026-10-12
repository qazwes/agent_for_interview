# 原型重构与代码阅读指南

本次实现四个页面：智能问数、应用配置、模型配置、回复校对。语音、登录/用户管理及入口不完整的日志/报表/台账/数据源功能不实现。保留原问数节点顺序，未增加 SQL 校验节点或合并模型调用。

## 按学习资料理解分层

参考「实战项目-电商问数」第 7 章知识库分层、第 14 章 SQL 闭环、第 15–16 章路由/依赖/Service 与第 17 章前后端联调：

```text
React 页面 / hooks
  → lib/productApi.ts 或 lib/agentApi.ts
  → API Router（接收 Schema、调用 Service、返回响应）
  → Service（编排查询、事务、关联和结果整理）
  → Repository（ORM / SQL 读写）
  → ClientManager 管理的 Engine / Session
  → MySQL / Qdrant / ES
```

`main.py` 注册路由；`app/api/dependencies.py` 组装依赖；`lifespan.py` 初始化和关闭客户端。应用库连接由 `conf/app_config.yaml` 的 `db_app` 声明，Compose 注入环境变量。`ApplicationService` 每次操作创建短事务，再将 Session 交给 `ApplicationRepository`，避免 SSE 等待期间持有应用库事务。

## 前端怎么读

| 文件 | 职责 |
| --- | --- |
| src/App.tsx | 组装四个页面，使用 hash 路由；问数页保持挂载 |
| src/components/AppLayout.tsx | 顶部与主导航，折叠状态 |
| src/pages/ChatPage.tsx | 欢迎页、输入区、消息与快捷提问 |
| src/hooks/useChat.ts | 问数状态、SSE 事件、会话加载与产品操作 |
| src/components/ConversationSidebar.tsx | 会话切换、置顶、重命名、删除 |
| src/components/AnswerCard.tsx | 分析过程、发现、表格、统计、可视化、反馈 |
| src/components/QueryChart.tsx | ECharts 柱状、折线、饼图；金额和比例使用不同坐标轴 |
| src/components/Modal.tsx | 弹窗外壳、关闭、焦点和键盘行为 |
| src/state/preferences.tsx | 本地配置共享状态和 localStorage |
| src/pages/AppConfigPage.tsx | 开场白、开场问题、建议/常问/模型入口开关 |
| src/pages/ModelConfigPage.tsx | 模型列表、测试、新增、保存选择 |
| src/pages/FeedbackPage.tsx | 反馈搜索、状态筛选、分页与处理 |

例如输入问题后：`ChatPage.send → useChat.submit → streamQuery → /api/query → onEvent → 更新 messages → AnswerCard 渲染`。刷新时从会话接口重新加载结构化消息，数据库不保存 HTML。

旧版 App、背景样式、Composer、EmptyState、MessageBubble、StepRail 已被替代并删除，Tailwind/PostCSS/Autoprefixer 依赖移除。图表模块按需加载。

## 后端怎么读

| 文件 | 职责 |
| --- | --- |
| app/api/schemas/application_schema.py | 产品接口请求字段校验 |
| app/api/routers/application_router.py | 会话、收藏、常问、模型和反馈路由 |
| app/services/application_service.py | 业务规则、短事务、问答及反馈关联 |
| app/repositories/mysql/application/application_repository.py | 应用表读写 |
| app/models/application.py | agent_app ORM 模型，独立 AppBase |
| app/services/query_service.py | 查询准备、模型固定、SSE 包装、结果持久化 |
| app/services/result_presenter.py | 最终 SQL + 实际结果 + 元数据 → 展示结构 |
| app/services/model_service.py | 模型连接测试和列表组织 |
| app/agent/llm.py | 模型工厂；请求内选中模型传入 Runtime Context |

原查询图不变；七个调用模型的节点改为从 Context 取本次模型，保留环境配置作为默认。

## 数据与接口

同一个 MySQL 容器包含 `dw`（分析数据）、`meta`（知识库定义）、`agent_app`（产品记录）。新增应用库无需运行元数据同步。

| 应用表 | 用途 |
| --- | --- |
| chat_session | 会话标题、置顶和时间 |
| chat_message | 用户问题、回答、真实结果 JSON、过程、状态、重发来源 |
| question_favorite | 收藏问题，以文本 hash 去重 |
| answer_feedback | 被反馈答案快照、处理状态和备注；删除会话仍保留快照 |
| model_config | 模型服务配置，密钥只保存在服务端，不返回浏览器 |
| app_setting | 当前选中模型 ID；其余显示配置保留在浏览器 |

应用表的权威部署 DDL 是 `docker/mysql/agent_app.sql`，不由数仓生成器覆盖。`zz-agent-app.sh` 和 `upgrade-app.*` 提供已有数据卷的幂等创建；不删除 DW/Meta，不重置密码。

| API | 行为 |
| --- | --- |
| POST /api/query | 请求 query、可选 session_id / source_message_id；旧请求仍有效 |
| GET /api/sessions?days=30 | 历史会话，按置顶和更新时间排序 |
| POST /api/sessions | 创建空会话 |
| GET /api/sessions/{id} | 会话和消息 |
| PATCH /api/sessions/{id} | 标题、置顶 |
| DELETE /api/sessions/{id} | 删除会话与消息，进行中查询返回 409 |
| GET / POST /api/favorites | 收藏列表、新增 |
| DELETE /api/favorites/{id} | 取消收藏 |
| GET /api/questions/frequent?threshold=3 | 用户问题出现次数严格超过阈值 |
| GET / POST /api/feedbacks | 反馈分页筛选、新增具体回答反馈 |
| PATCH /api/feedbacks/{id} | 处理状态 pending/resolved 与备注 |
| GET /api/models | 模型列表和 selected_id；包括现有环境配置 |
| POST /api/models/test | 真实连接测试，有效回复才成功 |
| POST /api/models | 新增服务端模型配置 |
| PUT /api/models/selection | 保存当前选择，下次查询生效 |

SSE 保留 `progress/result/error`，新增 `conversation` 返回真实会话/消息 ID。`result` 继续保留 `data`，补充 `presentation`、`elapsed_ms`、`model_name` 和 `message_id`。没有真实 Token 用量时不显示固定数字。

并行节点失败后，本次查询结束：失败节点保持 `error`，其他 `running` 步骤转为 `cancelled`（页面显示“已中断”）。`QueryService` 发送收尾进度再发错误，`ApplicationService` 保存终止状态并兼容旧历史；前端 `queryProgress.ts` 在错误、断流和停止时收尾，`agentApi.ts` 收到结果/错误即结束读取，不接收迟到事件。不会在业务层自动重跑问数，用户可通过重新发送追加问答。

## 数据发现如何实现

SQLGlot 仅用于读取 SQL 的表引用、投影和条件，不作为新增的安全校验。真实结果整理成字段说明、单位、统计、图表描述和规则建议。日期来自实际事实表最新日期，年度目标没有伪造截止日期。

排名合计仅表示返回记录的合计；比例、AVG、MIN、MAX 不累加。例：商业目标 TOP5 商业合计为 31,130 万，商解目标合计为 4,410 万，不采用原型中的固定 12%。单位与图表字段采用 SQL 和元数据推导；复杂表达式的展示语义仍需业务验收。

建议问题携带原问题的条件，不增加模型调用。会话历史保存不等于任意多轮语义理解：目前用户直接说“那上海呢”仍没有专门的上下文改写节点。建议问题用完整上下文表达。

## 验收顺序

先运行 `tests/` 的离线回归，再运行 `smoke_api.py`、`browser_smoke.mjs` 和 `browser_query_failure.mjs`。最后一个脚本全部模拟 API，用于验证并行失败、断流、停止和历史状态；不写数据库。真实模型端到端需显式指定 `--query`。详情见 [测试说明](../tests/README.md)。
