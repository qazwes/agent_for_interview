"""离线测试仅用占位配置，不读取真实服务或执行模型调用。"""
import os

for key in ("DB_META_PASSWORD", "DB_DW_PASSWORD", "DB_APP_PASSWORD", "LLM_API_KEY"):
    os.environ.setdefault(key, "test")
