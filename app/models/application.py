"""产品数据模型：独立于 DW 和知识库 Meta，消息保存数据而不是 HTML。"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_id():
    return str(uuid.uuid4())


class AppBase(DeclarativeBase):
    pass


class ChatSession(AppBase):
    __tablename__ = "chat_session"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(100), default="新对话")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ChatMessage(AppBase):
    __tablename__ = "chat_message"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(ForeignKey("chat_session.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="done")
    # 用 ID 关联问答和重发来源；重发追加记录，不删除旧答案。
    reply_to_id: Mapped[str | None] = mapped_column(String(36))
    source_message_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class QuestionFavorite(AppBase):
    __tablename__ = "question_favorite"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    question: Mapped[str] = mapped_column(Text)
    question_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AnswerFeedback(AppBase):
    __tablename__ = "answer_feedback"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    message_id: Mapped[str | None] = mapped_column(ForeignKey("chat_message.id", ondelete="SET NULL"))
    question: Mapped[str] = mapped_column(Text)
    # 保留被反馈答案的快照，即使原会话删除仍可处理反馈。
    answer: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    remark: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ModelProfile(AppBase):
    __tablename__ = "model_config"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(100))
    base_url: Mapped[str] = mapped_column(String(500))
    model_name: Mapped[str] = mapped_column(String(200))
    api_key: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AppSetting(AppBase):
    __tablename__ = "app_setting"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)
