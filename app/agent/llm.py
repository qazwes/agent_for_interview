"""
电商问数 Agent 使用的大模型实例

集中初始化 OpenAI 兼容的 Chat Model，供问数节点和模型连接测试复用
"""

from langchain.chat_models import init_chat_model

from app.conf.app_config import app_config


# 统一从配置读取模型三件套，节点只复用 llm，不重复初始化模型连接
def create_llm(profile=None):
    """每个请求固定模型配置；页面切换模型不会改变正在执行的请求。"""
    profile = profile or {}
    return init_chat_model(
    model=profile.get("model_name", app_config.llm.model_name),
    # 硅基流动等服务兼容 OpenAI 协议时，可以使用 openai provider 接入
    model_provider="openai",
    base_url=profile.get("base_url", app_config.llm.base_url),
    api_key=profile.get("api_key", app_config.llm.api_key),
    # 字段扩展、SQL 生成更看重稳定性，所以这里关闭随机发散
    temperature=0,
)


llm = create_llm()


def get_llm(context):
    return context.get("llm", llm)
