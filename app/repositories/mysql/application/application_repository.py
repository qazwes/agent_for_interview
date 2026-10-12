"""应用 MySQL 仓储：只负责 SQL / ORM 读写，不决定业务事务和 HTTP 响应。"""
from sqlalchemy import delete, func, select, update

from app.models.application import (
    AnswerFeedback,
    ChatMessage,
    ChatSession,
    QuestionFavorite,
)


class ApplicationRepository:
    def __init__(self, session):
        self.session = session

    async def get(self, model, id, lock=False):
        statement = select(model).where(model.id == id)
        if lock:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def save(self, row):
        self.session.add(row)
        await self.session.flush()
        return row

    async def sessions(self, since):
        return (await self.session.scalars(select(ChatSession).where(ChatSession.updated_at >= since)
            .order_by(ChatSession.pinned.desc(), ChatSession.updated_at.desc()))).all()

    async def messages(self, id):
        return (await self.session.scalars(select(ChatMessage).where(ChatMessage.session_id == id)
            .order_by(ChatMessage.created_at, ChatMessage.id))).all()

    async def running_message(self, id):
        return await self.session.scalar(select(ChatMessage.id).where(
            ChatMessage.session_id == id, ChatMessage.status == "streaming"))

    async def delete_session(self, row):
        ids = select(ChatMessage.id).where(ChatMessage.session_id == row.id)
        await self.session.execute(update(AnswerFeedback).where(AnswerFeedback.message_id.in_(ids)).values(message_id=None))
        await self.session.execute(delete(ChatMessage).where(ChatMessage.session_id == row.id))
        await self.session.delete(row)

    async def favorites(self):
        return (await self.session.scalars(select(QuestionFavorite).order_by(QuestionFavorite.created_at.desc()))).all()

    async def favorite_by_hash(self, digest):
        return await self.session.scalar(select(QuestionFavorite).where(QuestionFavorite.question_hash == digest))

    async def delete(self, row):
        await self.session.delete(row)

    async def frequent(self, threshold):
        count = func.count(ChatMessage.id).label("count")
        statement = select(ChatMessage.content.label("question"), count).where(ChatMessage.role == "user")
        statement = statement.group_by(ChatMessage.content).having(count > threshold).order_by(count.desc(), ChatMessage.content).limit(30)
        return [dict(row) for row in (await self.session.execute(statement)).mappings()]

    def feedback_conditions(self, q, status):
        conditions = []
        if q:
            conditions.append(AnswerFeedback.question.contains(q, autoescape=True))
        if status != "all":
            conditions.append(AnswerFeedback.status == status)
        return conditions

    async def feedback_count(self, q, status):
        return await self.session.scalar(select(func.count()).select_from(AnswerFeedback).where(*self.feedback_conditions(q, status)))

    async def feedbacks(self, q, status, page, page_size):
        return (await self.session.scalars(select(AnswerFeedback).where(*self.feedback_conditions(q, status))
            .order_by(AnswerFeedback.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()

    async def all_models(self, model):
        return (await self.session.scalars(select(model).order_by(model.created_at))).all()

    async def setting(self, model, key):
        return await self.session.get(model, key)

    async def recover_interrupted(self):
        await self.session.execute(update(ChatMessage).where(ChatMessage.status == "streaming").values(
            status="error", content="服务已重启，本次查询未完成，请重新发送。"))
