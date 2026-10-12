"""??????????????? Pydantic?"""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class SessionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    pinned: bool | None = None

    @field_validator("title")
    @classmethod
    def clean_title(cls, value):
        if value is not None and not value.strip():
            raise ValueError("标题不能为空")
        return value.strip() if value is not None else None


class QuestionBody(BaseModel):
    question: str = Field(min_length=1, max_length=4000)

    @field_validator("question")
    @classmethod
    def clean(cls, value):
        if not value.strip():
            raise ValueError("问题不能为空")
        return value.strip()


class FeedbackBody(BaseModel):
    message_id: str


class FeedbackPatch(BaseModel):
    status: Literal["pending", "resolved"]
    remark: str = Field(default="", max_length=5000)


class ModelBody(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    base_url: str = Field(min_length=1, max_length=500)
    model_name: str = Field(min_length=1, max_length=200)
    api_key: str = Field(min_length=1, max_length=4000)

    @field_validator("name", "base_url", "model_name", "api_key")
    @classmethod
    def clean(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("字段不能为空")
        return value

    @field_validator("base_url")
    @classmethod
    def check_url(cls, value):
        from urllib.parse import urlsplit
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("请填写不含凭据的 HTTP/HTTPS 服务地址")
        return value.rstrip("/")


class ModelSelection(BaseModel):
    model_id: str


