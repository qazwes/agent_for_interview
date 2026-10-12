"""可直接运行：python tests/smoke_api.py [--query '实际问题']。

默认只验证产品 API，不调用 LLM。--query 才调用当前真实模型。
测试仅删除自己创建的会话和收藏；真实问数与反馈记录保留供界面核对。
"""
import argparse
import json
import uuid
from urllib.request import ProxyHandler, Request, build_opener


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8080")
    parser.add_argument("--query", help="可选：执行真实问数（会调用当前模型）")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    # 验收直接访问指定环境，不走宿主机器的全局 HTTP 代理。
    urlopen = build_opener(ProxyHandler({})).open

    def call(method, path, body=None):
        request = Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                          headers={"Content-Type": "application/json"}, method=method)
        with urlopen(request, timeout=15) as response:
            data = response.read()
            return json.loads(data) if data else None

    session_id = favorite_id = None
    try:
        assert call("GET", "/health")["status"] == "ok"
        print("[PASS] API health")
        with urlopen(base, timeout=10) as response:
            assert b'/assets/' in response.read()
        print("[PASS] React page served")
        session = call("POST", "/api/sessions")
        session_id = session["id"]
        call("PATCH", f"/api/sessions/{session_id}", {"title": "验收测试会话", "pinned": True})
        assert call("GET", f"/api/sessions/{session_id}")["title"] == "验收测试会话"
        assert any(s["id"] == session_id for s in call("GET", "/api/sessions"))
        print("[PASS] Create / rename / pin / load session")
        favorite = call("POST", "/api/favorites", {"question": "验收问题-" + str(uuid.uuid4())})
        favorite_id = favorite["id"]
        assert any(f["id"] == favorite_id for f in call("GET", "/api/favorites"))
        call("DELETE", f"/api/favorites/{favorite_id}")
        favorite_id = None
        print("[PASS] Favorite persistence")
        assert isinstance(call("GET", "/api/questions/frequent?threshold=3"), list)
        assert "api_key" not in json.dumps(call("GET", "/api/models"))
        assert "items" in call("GET", "/api/feedbacks")
        print("[PASS] Frequent questions / model list / feedback list")
        call("DELETE", f"/api/sessions/{session_id}")
        session_id = None
        print("[PASS] Delete test session")
        if args.query:
            request = Request(base + "/api/query", data=json.dumps({"query": args.query}).encode(),
                              headers={"Content-Type": "application/json", "Accept": "text/event-stream"})
            result = None
            with urlopen(request, timeout=330) as response:
                for raw in response:
                    line = raw.decode("utf-8").strip()
                    if not line.startswith("data:"):
                        continue
                    event = json.loads(line[5:].strip())
                    if event["type"] == "error":
                        raise AssertionError(event["message"])
                    if event["type"] == "conversation":
                        query_session = event["session_id"]
                    if event["type"] == "result":
                        result = event
            assert result is not None, "SSE 没有 result"
            assert result["presentation"]["sql"]
            saved = call("GET", f"/api/sessions/{query_session}")["messages"][-1]
            assert saved["payload"]["data"] == result["data"]
            print(f"[PASS] Real query / presentation / history: {len(result['data'])} rows")
            feedback = call("POST", "/api/feedbacks", {"message_id": result["message_id"]})
            call("PATCH", f"/api/feedbacks/{feedback['id']}", {"status": "resolved", "remark": "验收脚本：反馈链路通过"})
            print("[PASS] Feedback linked to actual answer; record retained")
        print("All checks passed.")
    finally:
        if favorite_id:
            call("DELETE", f"/api/favorites/{favorite_id}")
        if session_id:
            call("DELETE", f"/api/sessions/{session_id}")


if __name__ == "__main__":
    main()
