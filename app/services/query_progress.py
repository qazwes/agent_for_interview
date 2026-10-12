"""查询终止时收尾尚未完成的进度，不把中断误标为成功或失败。"""


def close_running_steps(steps):
    return [
        {**step, "status": "cancelled"} if step["status"] == "running" else step
        for step in steps
    ]


def close_progress_payload(payload):
    if not payload or "steps" not in payload:
        return payload
    return {**payload, "steps": close_running_steps(payload["steps"])}
