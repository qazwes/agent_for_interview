import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from app.services.model_service import ModelService


def test_connection_requires_actual_content_and_hides_upstream_secrets():
    async def run():
        service = ModelService(None)
        model = Mock()
        model.ainvoke = AsyncMock(return_value=SimpleNamespace(content="连接成功"))
        with patch("app.services.model_service.create_llm", return_value=model):
            assert (await service.test_connection({}))["ok"] is True
        model.ainvoke = AsyncMock(return_value=SimpleNamespace(content=""))
        with patch("app.services.model_service.create_llm", return_value=model):
            with pytest.raises(HTTPException):
                await service.test_connection({})
        model.ainvoke = AsyncMock(side_effect=RuntimeError("Authorization: secret-test-key"))
        with patch("app.services.model_service.create_llm", return_value=model):
            with pytest.raises(HTTPException) as error:
                await service.test_connection({})
            assert "secret-test-key" not in error.value.detail
    asyncio.run(run())
