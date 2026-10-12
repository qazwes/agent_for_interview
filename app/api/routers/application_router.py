"""会话、收藏、常问、反馈、模型配置接口。显示偏好留在前端。"""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_application_service, get_model_service
from app.api.schemas.application_schema import (
    FeedbackBody,
    FeedbackPatch,
    ModelBody,
    ModelSelection,
    QuestionBody,
    SessionPatch,
)

application_router = APIRouter(prefix="/api")


@application_router.get("/sessions")
async def list_sessions(days: int = Query(30, ge=1, le=3650), store=Depends(get_application_service)):
    return await store.sessions(days)


@application_router.post("/sessions", status_code=201)
async def create_session(store=Depends(get_application_service)):
    return await store.create_session()


@application_router.get("/sessions/{id}")
async def get_session(id: str, store=Depends(get_application_service)):
    return await store.session_detail(id)


@application_router.patch("/sessions/{id}")
async def patch_session(id: str, body: SessionPatch, store=Depends(get_application_service)):
    return await store.patch_session(id, body.model_dump(exclude_none=True))


@application_router.delete("/sessions/{id}", status_code=204)
async def delete_session(id: str, store=Depends(get_application_service)):
    await store.delete_session(id)
    return Response(status_code=204)


@application_router.get("/favorites")
async def favorites(store=Depends(get_application_service)):
    return await store.favorites()


@application_router.post("/favorites", status_code=201)
async def add_favorite(body: QuestionBody, store=Depends(get_application_service)):
    return await store.favorite(body.question)


@application_router.delete("/favorites/{id}", status_code=204)
async def delete_favorite(id: str, store=Depends(get_application_service)):
    await store.delete_favorite(id)
    return Response(status_code=204)


@application_router.get("/questions/frequent")
async def frequent(threshold: int = Query(3, ge=1, le=100000), store=Depends(get_application_service)):
    return await store.frequent(threshold)


@application_router.post("/feedbacks", status_code=201)
async def create_feedback(body: FeedbackBody, store=Depends(get_application_service)):
    return await store.create_feedback(body.message_id)


@application_router.get("/feedbacks")
async def feedbacks(q: str = "", status: Literal["all", "pending", "resolved"] = "all",
                    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=100),
                    store=Depends(get_application_service)):
    return await store.feedbacks(q, status, page, page_size)


@application_router.patch("/feedbacks/{id}")
async def patch_feedback(id: str, body: FeedbackPatch, store=Depends(get_application_service)):
    return await store.patch_feedback(id, body.model_dump())


@application_router.get("/models")
async def models(service=Depends(get_model_service)):
    return await service.list_models()


@application_router.post("/models/test")
async def test_model(body: ModelBody, service=Depends(get_model_service)):
    return await service.test_connection(body.model_dump())


@application_router.post("/models", status_code=201)
async def add_model(body: ModelBody, store=Depends(get_application_service)):
    return await store.add_model(body.model_dump())


@application_router.put("/models/selection")
async def select_model(body: ModelSelection, store=Depends(get_application_service)):
    await store.select_model(body.model_id)
    return {"selected_id": body.model_id}
