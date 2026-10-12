"""
问数查询服务

负责把 API 层传入的自然语言问题转换成一次 LangGraph 工作流执行：
创建初始 State、组装 Runtime Context、消费 graph.astream 的流式输出，
并统一包装成 SSE 文本返回给路由层。
"""

import asyncio
import json
from time import perf_counter

from langchain_huggingface import HuggingFaceEndpointEmbeddings

from app.agent.context import DataAgentContext
from app.agent.graph import graph
from app.agent.llm import create_llm
from app.agent.state import DataAgentState
from app.repositories.es.value_es_repository import ValueESRepository
from app.repositories.mysql.dw.dw_mysql_repository import DWMySQLRepository
from app.repositories.mysql.meta.meta_mysql_repository import MetaMySQLRepository
from app.repositories.qdrant.column_qdrant_repository import ColumnQdrantRepository
from app.repositories.qdrant.metric_qdrant_repository import MetricQdrantRepository
from app.services.query_progress import close_running_steps


class QueryService:
    """封装一次问数查询所需的业务编排逻辑"""

    def __init__(
        self,
        meta_mysql_repository: MetaMySQLRepository,
        embedding_client: HuggingFaceEndpointEmbeddings,
        dw_mysql_repository: DWMySQLRepository,
        column_qdrant_repository: ColumnQdrantRepository,
        metric_qdrant_repository: MetricQdrantRepository,
        value_es_repository: ValueESRepository,
        application_service=None,
    ):
        # MySQL 仓储分别负责元数据补全和真实数仓环境信息读取
        self.meta_mysql_repository = meta_mysql_repository
        self.dw_mysql_repository = dw_mysql_repository

        # 召回链路依赖的向量检索、Embedding 和全文检索能力由依赖层注入
        self.embedding_client = embedding_client
        self.column_qdrant_repository = column_qdrant_repository
        self.metric_qdrant_repository = metric_qdrant_repository
        self.value_es_repository = value_es_repository
        self.application_service = application_service

    async def prepare(self, query, session_id=None, source_message_id=None):
        """在建立 SSE 连接前验证会话，保存问答并固定本次模型配置。"""
        profile = await self.application_service.selected_model()
        if session_id is None:
            session_id = (await self.application_service.create_session())["id"]
        prepared = await self.application_service.begin_query(session_id, query, source_message_id)
        prepared["profile"] = profile
        return prepared

    async def query(self, query: str, prepared=None):
        """执行一次问数工作流，并逐段产出 SSE 消息"""

        # State 只放会被图节点读写和合并的业务数据，外部工具对象不塞进 State
        state = DataAgentState(query=query)
        # Context 保存本次图执行需要复用的外部依赖，节点通过 runtime.context 读取
        context = DataAgentContext(
            column_qdrant_repository=self.column_qdrant_repository,
            embedding_client=self.embedding_client,
            metric_qdrant_repository=self.metric_qdrant_repository,
            value_es_repository=self.value_es_repository,
            meta_mysql_repository=self.meta_mysql_repository,
            dw_mysql_repository=self.dw_mysql_repository,
        )
        from app.conf.app_config import app_config
        profile = prepared.get("profile") if prepared else None
        if profile:
            context["llm"] = create_llm(profile)
        model_name = profile["model_name"] if profile else app_config.llm.model_name
        steps, result_event = [], None
        started = perf_counter()
        answer_id = prepared["assistant"]["id"] if prepared else None
        def encode(event):
            return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
        try:
            if prepared:
                yield encode({"type": "conversation", "session_id": prepared["session_id"],
                              "user": prepared["user"], "assistant": prepared["assistant"]})
            # stream_mode="custom" 对应节点内部 writer(...) 写出的进度消息
            async for chunk in graph.astream(
                input=state, context=context, stream_mode="custom"
            ):
                # SSE 要求每条消息以 data: 开头，并以两个换行符结束
                # ensure_ascii=False 保留中文进度文案，default=str 兜底处理日期等非 JSON 类型
                if chunk["type"] == "progress":
                    steps = [s for s in steps if s["step"] != chunk["step"]]
                    steps.append(chunk)
                if chunk["type"] == "result":
                    chunk.update({"elapsed_ms": round((perf_counter() - started) * 1000),
                                  "model_name": model_name, "message_id": answer_id})
                    result_event = chunk
                    if answer_id:
                        await self.application_service.finish_query(answer_id, "done",
                            f"查询完成，共 {len(chunk['data'])} 条结果。", {**chunk, "steps": steps})
                yield encode(chunk)
            if result_event is None:
                raise RuntimeError("流程已结束，但没有返回查询结果")
        except (asyncio.CancelledError, GeneratorExit):
            if answer_id and result_event is None:
                steps = close_running_steps(steps)
                await asyncio.shield(self.application_service.finish_query(
                    answer_id, "cancelled", "已停止本次查询。", {"steps": steps, "model_name": model_name}))
            raise
        except Exception as e:
            # 流式接口已经开始返回后不能再改 HTTP 状态码，因此把异常也包装成一条 SSE 消息
            interrupted = close_running_steps([s for s in steps if s["status"] == "running"])
            steps = close_running_steps(steps)
            error = {"type": "error", "message": str(e)}
            if answer_id:
                await self.application_service.finish_query(answer_id, "error", "查询失败。",
                    {"steps": steps, "error": str(e), "model_name": model_name})
            # 并行节点可能已被取消，未发出自己的终止事件；统一通知前端停止转圈。
            for step in interrupted:
                yield encode({"type": "progress", **step})
            yield encode(error)
