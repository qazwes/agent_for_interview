"""模型业务层：读取当前选择，测试实际连接，避免路由直接调用推理。"""
import asyncio

from fastapi import HTTPException

from app.agent.llm import create_llm
from app.conf.app_config import app_config


class ModelService:
    def __init__(self, application_service):
        self.application_service = application_service

    async def list_models(self):
        selected = await self.application_service.selected_model()
        env = {"id": "env", "name": app_config.llm.model_name + "（环境配置）",
               "model_name": app_config.llm.model_name, "base_url": app_config.llm.base_url}
        return {"items": [env, *await self.application_service.models()], "selected_id": selected["id"] if selected else "env"}

    async def test_connection(self, profile):
        try:
            response = await asyncio.wait_for(create_llm(profile).ainvoke("请回复：连接成功"), timeout=45)
            if not response.content:
                raise ValueError("empty response")
        except Exception:
            raise HTTPException(400, "模型连接测试失败，请检查服务地址、密钥和模型名称。") from None
        return {"ok": True, "message": "模型已返回有效回复"}
