"""产品业务层：组织短事务、校验会话归属、关联问答与反馈，再调用仓储读写。"""
import hashlib
import math
from datetime import timedelta

from fastapi import HTTPException

from app.models.application import (
    AnswerFeedback,
    AppSetting,
    ChatMessage,
    ChatSession,
    ModelProfile,
    QuestionFavorite,
    now,
)
from app.repositories.mysql.application.application_repository import (
    ApplicationRepository,
)
from app.services.query_progress import close_progress_payload


def serialize(row):
    data = {column.name: getattr(row, column.name) for column in row.__table__.columns}
    for key in ("created_at", "updated_at"):
        if key in data:
            data[key] = data[key].isoformat() + "Z"
    data.pop("api_key", None)
    # 兼容旧版本已结束却遗留 running 步骤的历史记录，无需迁移或清空数据。
    if isinstance(row, ChatMessage) and row.status != "streaming":
        data["payload"] = close_progress_payload(row.payload)
    return data


class ApplicationService:
    def __init__(self, factory):
        # SSE 中多次保存各用短事务；不让数据库会话覆盖整段模型等待时间。
        self.factory = factory

    async def require(self, repo, model, id, lock=False):
        row = await repo.get(model, id, lock)
        if row is None:
            raise HTTPException(404, "记录不存在")
        return row

    async def create_session(self):
        async with self.factory.begin() as session:
            return serialize(await ApplicationRepository(session).save(ChatSession()))

    async def sessions(self, days=30):
        async with self.factory() as session:
            return [serialize(row) for row in await ApplicationRepository(session).sessions(now() - timedelta(days=days))]

    async def session_detail(self, id):
        async with self.factory() as session:
            repo = ApplicationRepository(session)
            row = await self.require(repo, ChatSession, id)
            return {**serialize(row), "messages": [serialize(m) for m in await repo.messages(id)]}

    async def patch_session(self, id, values):
        async with self.factory.begin() as session:
            row = await self.require(ApplicationRepository(session), ChatSession, id)
            for key, value in values.items():
                setattr(row, key, value)
            return serialize(row)

    async def delete_session(self, id):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            row = await self.require(repo, ChatSession, id, lock=True)
            if await repo.running_message(id):
                raise HTTPException(409, "请先停止查询，再删除会话")
            await repo.delete_session(row)

    async def begin_query(self, session_id, question, source_message_id=None):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            row = await self.require(repo, ChatSession, session_id, lock=True)
            if await repo.running_message(session_id):
                raise HTTPException(409, "该会话已有查询正在进行")
            if source_message_id:
                source = await self.require(repo, ChatMessage, source_message_id)
                if source.session_id != session_id or source.role != "user":
                    raise HTTPException(400, "重发来源必须是当前会话的用户问题")
            user = await repo.save(ChatMessage(session_id=session_id, role="user", content=question,
                                              source_message_id=source_message_id))
            answer = await repo.save(ChatMessage(session_id=session_id, role="assistant", content="正在处理问题…",
                status="streaming", reply_to_id=user.id, payload={"steps": []}))
            if row.title == "新对话":
                row.title = question[:40]
            row.updated_at = now()
            return {"session_id": row.id, "user": serialize(user), "assistant": serialize(answer)}

    async def finish_query(self, id, status, content, payload):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            message = await self.require(repo, ChatMessage, id)
            message.status, message.content = status, content
            message.payload = close_progress_payload(payload) if status != "streaming" else payload
            conversation = await self.require(repo, ChatSession, message.session_id)
            conversation.updated_at = now()

    async def favorites(self):
        async with self.factory() as session:
            return [serialize(row) for row in await ApplicationRepository(session).favorites()]

    async def favorite(self, question):
        digest = hashlib.sha256(question.encode()).hexdigest()
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            row = await repo.favorite_by_hash(digest)
            if row is None:
                row = await repo.save(QuestionFavorite(question=question, question_hash=digest))
            return serialize(row)

    async def delete_favorite(self, id):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            await repo.delete(await self.require(repo, QuestionFavorite, id))

    async def frequent(self, threshold):
        async with self.factory() as session:
            return await ApplicationRepository(session).frequent(threshold)

    async def create_feedback(self, message_id):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            answer = await self.require(repo, ChatMessage, message_id)
            if answer.role != "assistant" or answer.status != "done":
                raise HTTPException(400, "请选择已完成的回答提交反馈")
            user = await self.require(repo, ChatMessage, answer.reply_to_id)
            return serialize(await repo.save(AnswerFeedback(message_id=message_id, question=user.content,
                answer={"content": answer.content, "payload": answer.payload})))

    async def feedbacks(self, q, status, page, page_size):
        async with self.factory() as session:
            repo = ApplicationRepository(session)
            total = await repo.feedback_count(q, status)
            page = min(page, max(1, math.ceil(total / page_size)))
            return {"items": [serialize(row) for row in await repo.feedbacks(q, status, page, page_size)], "total": total, "page": page}

    async def patch_feedback(self, id, values):
        async with self.factory.begin() as session:
            row = await self.require(ApplicationRepository(session), AnswerFeedback, id)
            for key, value in values.items():
                setattr(row, key, value)
            return serialize(row)

    async def models(self):
        async with self.factory() as session:
            return [serialize(row) for row in await ApplicationRepository(session).all_models(ModelProfile)]

    async def add_model(self, values):
        async with self.factory.begin() as session:
            return serialize(await ApplicationRepository(session).save(ModelProfile(**values)))

    async def selected_model(self):
        async with self.factory() as session:
            repo = ApplicationRepository(session)
            setting = await repo.setting(AppSetting, "query_model_id")
            if setting is None or setting.value == "env":
                return None
            profile = await self.require(repo, ModelProfile, setting.value)
            return {c.name: getattr(profile, c.name) for c in profile.__table__.columns}

    async def select_model(self, id):
        async with self.factory.begin() as session:
            repo = ApplicationRepository(session)
            if id != "env":
                await self.require(repo, ModelProfile, id)
            setting = await repo.setting(AppSetting, "query_model_id")
            if setting is None:
                await repo.save(AppSetting(key="query_model_id", value=id))
            else:
                setting.value = id

    async def recover_interrupted(self):
        async with self.factory.begin() as session:
            await ApplicationRepository(session).recover_interrupted()
