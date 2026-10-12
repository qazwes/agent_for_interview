"""应用业务回归：临时 SQLite 测试事务、归属、反馈快照和重发记录。"""
import asyncio

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.application import AppBase, ChatMessage
from app.services.application_service import ApplicationService


async def scenario(callback):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(AppBase.metadata.create_all)
    service = ApplicationService(async_sessionmaker(engine, expire_on_commit=False))
    try:
        await callback(service)
    finally:
        await engine.dispose()


def test_session_messages_resend_feedback_snapshot_and_delete():
    async def run(service):
        conversation = await service.create_session()
        first = await service.begin_query(conversation["id"], "2026年商业目标TOP5")
        with pytest.raises(HTTPException) as failure:
            await service.delete_session(conversation["id"])
        assert failure.value.status_code == 409
        await service.finish_query(first["assistant"]["id"], "done", "5条结果", {"data": [{"商业目标": 7950}]})
        feedback = await service.create_feedback(first["assistant"]["id"])
        second = await service.begin_query(conversation["id"], "2026年商业目标TOP3", first["user"]["id"])
        await service.finish_query(second["assistant"]["id"], "done", "3条结果", {"data": []})
        detail = await service.session_detail(conversation["id"])
        assert len(detail["messages"]) == 4
        assert detail["messages"][0]["content"] == "2026年商业目标TOP5"
        assert detail["messages"][2]["source_message_id"] == first["user"]["id"]
        await service.patch_session(conversation["id"], {"title": "目标分析", "pinned": True})
        assert (await service.sessions())[0]["title"] == "目标分析"
        await service.patch_feedback(feedback["id"], {"status": "resolved", "remark": "已核对"})
        await service.delete_session(conversation["id"])
        assert await service.sessions() == []
        saved = (await service.feedbacks("TOP5", "resolved", 1, 10))["items"][0]
        assert saved["message_id"] is None
        assert saved["answer"]["payload"]["data"][0]["商业目标"] == 7950
    asyncio.run(scenario(run))


def test_old_terminal_messages_close_progress_without_changing_live_queries():
    async def run(service):
        conversation = await service.create_session()
        first = await service.begin_query(conversation["id"], "旧版失败记录")
        # 直接写入旧版 payload，避免新 finish_query 收尾掩盖历史兼容问题。
        steps = [{"step": "过滤表信息", "status": "running"},
                 {"step": "过滤指标信息", "status": "error"}]
        async with service.factory.begin() as session:
            row = await session.get(ChatMessage, first["assistant"]["id"])
            row.status, row.payload = "error", {"steps": steps, "error": "上游 502"}
        detail = await service.session_detail(conversation["id"])
        assert detail["messages"][-1]["payload"]["steps"] == [
            {"step": "过滤表信息", "status": "cancelled"},
            {"step": "过滤指标信息", "status": "error"},
        ]
        assert detail["messages"][-1]["payload"]["error"] == "上游 502"
        live = await service.begin_query(conversation["id"], "正在执行的新查询")
        async with service.factory.begin() as session:
            row = await session.get(ChatMessage, live["assistant"]["id"])
            row.payload = {"steps": [{"step": "过滤表信息", "status": "running"}]}
        assert (await service.session_detail(conversation["id"]))["messages"][-1]["payload"]["steps"][0]["status"] == "running"

    asyncio.run(scenario(run))


def test_frequency_favorite_and_message_ownership():
    async def run(service):
        a, b = await service.create_session(), await service.create_session()
        first = await service.begin_query(a["id"], "北京收入")
        await service.finish_query(first["assistant"]["id"], "done", "结果", {"data": []})
        with pytest.raises(HTTPException) as failure:
            await service.begin_query(b["id"], "修改问题", first["user"]["id"])
        assert failure.value.status_code == 400
        assert (await service.session_detail(b["id"]))["messages"] == []
        for _ in range(3):
            item = await service.begin_query(a["id"], "北京收入")
            await service.finish_query(item["assistant"]["id"], "done", "结果", {"data": []})
        assert await service.frequent(3) == [{"question": "北京收入", "count": 4}]
        assert await service.frequent(4) == []
        f1, f2 = await service.favorite("北京收入"), await service.favorite("北京收入")
        assert f1["id"] == f2["id"]
        assert len(await service.favorites()) == 1
        await service.delete_favorite(f1["id"])
        assert await service.favorites() == []
    asyncio.run(scenario(run))


def test_model_secret_not_returned_and_restart_recovery():
    async def run(service):
        profile = await service.add_model({"name": "测试模型", "base_url": "https://example.test/v1", "model_name": "test-model", "api_key": "private-test-key"})
        assert "api_key" not in profile
        assert "api_key" not in (await service.models())[0]
        await service.select_model(profile["id"])
        assert (await service.selected_model())["api_key"] == "private-test-key"
        await service.select_model("env")
        assert await service.selected_model() is None
        c = await service.create_session()
        await service.begin_query(c["id"], "未完成的查询")
        await service.recover_interrupted()
        assert (await service.session_detail(c["id"]))["messages"][-1]["status"] == "error"
    asyncio.run(scenario(run))
