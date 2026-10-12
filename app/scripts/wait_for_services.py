"""启动 API 或构建元数据前，等待 Compose 内部依赖就绪。"""

import os
import socket
import time
from urllib.request import urlopen

from app.conf.app_config import app_config


def unavailable_services() -> list[str]:
    """检测依赖，不输出密码或模型密钥。"""
    unavailable = []
    try:
        with socket.create_connection(
            (app_config.db_dw.host, app_config.db_dw.port), timeout=3
        ):
            pass
    except OSError:
        unavailable.append("mysql")

    endpoints = {
        "elasticsearch": f"http://{app_config.es.host}:{app_config.es.port}/_cluster/health",
        "qdrant": f"http://{app_config.qdrant.host}:{app_config.qdrant.port}/readyz",
        "embedding": f"http://{app_config.embedding.host}:{app_config.embedding.port}/health",
    }
    for name, endpoint in endpoints.items():
        try:
            with urlopen(endpoint, timeout=3) as response:
                if response.status != 200:
                    unavailable.append(name)
        except OSError:
            unavailable.append(name)
    return unavailable


def main() -> None:
    deadline = time.monotonic() + float(os.getenv("DEPENDENCY_WAIT_SECONDS", "180"))
    while True:
        unavailable = unavailable_services()
        if not unavailable:
            print("All dependencies are ready.", flush=True)
            return
        if time.monotonic() >= deadline:
            raise SystemExit("Dependencies did not become ready: " + ", ".join(unavailable))
        print("Waiting for: " + ", ".join(unavailable), flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
