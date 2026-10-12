"""替换图输出验证真实 SSE 包装、持久化、错误和取消，不调用付费模型。"""
import asyncio
import json
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.application import AppBase, ChatMessage
from app.services.application_service import ApplicationService
from app.services.query_service import QueryService


def events(chunks):
    return [json.loads(chunk.removeprefix("data: ").strip()) for chunk in chunks]


def test_sse_persists_exact_result_and_model_selection():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as c:
            await c.run_sync(AppBase.metadata.create_all)
        store = ApplicationService(async_sessionmaker(engine, expire_on_commit=False))
        service = QueryService(None, None, None, None, None, None, store)
        captured = {}
        async def fake_graph(**kwargs):
            captured.update(kwargs)
            yield {"type": "progress", "step": "执行SQL", "status": "success"}
            yield {"type": "result", "data": [{"收入": 2647.5}], "presentation": {"sql": "SELECT 2647.5"}}
        with patch("app.services.query_service.graph.astream", fake_graph):
            prepared = await service.prepare("北京收入")
            output = events([chunk async for chunk in service.query("北京收入", prepared)])
        assert output[0]["type"] == "conversation"
        assert output[-1]["data"] == [{"收入": 2647.5}]
        detail = await store.session_detail(prepared["session_id"])
        assert detail["messages"][-1]["payload"]["data"] == output[-1]["data"]
        assert detail["messages"][-1]["status"] == "done"
        assert captured["input"]["query"] == "北京收入"
        await engine.dispose()
    asyncio.run(run())


def test_error_and_cancel_leave_no_streaming_message():
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as c:
            await c.run_sync(AppBase.metadata.create_all)
        store = ApplicationService(async_sessionmaker(engine, expire_on_commit=False))
        service = QueryService(None, None, None, None, None, None, store)
        async def failure(**kwargs):
            yield {"type": "progress", "step": "抽取关键词", "status": "success"}
            yield {"type": "progress", "step": "过滤表信息", "status": "running"}
            yield {"type": "progress", "step": "过滤指标信息", "status": "running"}
            yield {"type": "progress", "step": "过滤指标信息", "status": "error"}
            raise RuntimeError("模拟模型错误")
        with patch("app.services.query_service.graph.astream", failure):
            prepared = await service.prepare("失败测试")
            output = events([chunk async for chunk in service.query("失败测试", prepared)])
            assert output[-1]["type"] == "error"
            assert output[-2] == {"type": "progress", "step": "过滤表信息", "status": "cancelled"}
        assert (await store.session_detail(prepared["session_id"]))["messages"][-1]["status"] == "error"
        async with store.factory() as session:
            saved = await session.get(ChatMessage, prepared["assistant"]["id"])
            assert saved.payload["steps"] == [
                {"type": "progress", "step": "抽取关键词", "status": "success"},
                {"type": "progress", "step": "过滤表信息", "status": "cancelled"},
                {"type": "progress", "step": "过滤指标信息", "status": "error"},
            ]
        async def cancelled(**kwargs):
            yield {"type": "progress", "step": "过滤表信息", "status": "running"}
            yield {"type": "progress", "step": "过滤指标信息", "status": "running"}
            raise asyncio.CancelledError()
        with patch("app.services.query_service.graph.astream", cancelled):
            prepared = await service.prepare("取消测试")
            with pytest.raises(asyncio.CancelledError):
                _ = [chunk async for chunk in service.query("取消测试", prepared)]
        assert (await store.session_detail(prepared["session_id"]))["messages"][-1]["status"] == "cancelled"
        async with store.factory() as session:
            saved = await session.get(ChatMessage, prepared["assistant"]["id"])
            assert all(step["status"] == "cancelled" for step in saved.payload["steps"])
        await engine.dispose()
    asyncio.run(run())


@pytest.mark.parametrize("close_stream", [False, True], ids=["unexpected-eof", "client-disconnect"])
def test_unfinished_stream_closes_steps_and_allows_resend(close_stream):
    async def run():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        try:
            async with engine.begin() as connection:
                await connection.run_sync(AppBase.metadata.create_all)
            store = ApplicationService(async_sessionmaker(engine, expire_on_commit=False))
            service = QueryService(None, None, None, None, None, None, store)

            async def incomplete_graph(**kwargs):
                yield {"type": "progress", "step": "过滤表信息", "status": "running"}

            with patch("app.services.query_service.graph.astream", incomplete_graph):
                prepared = await service.prepare("中断后重新发送")
                stream = service.query("中断后重新发送", prepared)
                if close_stream:
                    assert events([await anext(stream)])[0]["type"] == "conversation"
                    assert events([await anext(stream)])[0]["status"] == "running"
                    await stream.aclose()
                else:
                    output = events([chunk async for chunk in stream])
                    assert output[-1]["type"] == "error"
                    assert "没有返回查询结果" in output[-1]["message"]

            async with store.factory() as session:
                saved = await session.get(ChatMessage, prepared["assistant"]["id"])
                assert saved.status == ("cancelled" if close_stream else "error")
                assert saved.payload["steps"][0]["status"] == "cancelled"
            retry = await store.begin_query(prepared["session_id"], "手动重新发送", prepared["user"]["id"])
            await store.finish_query(retry["assistant"]["id"], "cancelled", "测试结束", {"steps": []})
            assert len((await store.session_detail(prepared["session_id"]))["messages"]) == 4
        finally:
            await engine.dispose()

    asyncio.run(run())
