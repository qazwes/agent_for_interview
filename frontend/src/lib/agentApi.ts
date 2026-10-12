/**
 * 智能体接口客户端
 * 封装后端 /api/query SSE 流式接口请求与事件解析逻辑
 */
import type { AgentEvent } from "../types/agent";

import { API_BASE_URL } from "./productApi";

type QueryOptions = {
  signal?: AbortSignal;
  onEvent: (event: AgentEvent) => void;
  sessionId?: string;
  sourceMessageId?: string;
};

export async function streamQuery(query: string, options: QueryOptions) {
  const response = await fetch(`${API_BASE_URL}/api/query`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify({ query, session_id: options.sessionId, source_message_id: options.sourceMessageId }),
    signal: options.signal,
  });

  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `接口请求失败：HTTP ${response.status}`);
  }

  if (!response.body) {
    throw new Error("浏览器未返回可读取的流式响应。");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split(/\r?\n\r?\n/);
      buffer = chunks.pop() ?? "";

      for (const chunk of chunks) {
        const event = parseSseChunk(chunk);
        if (event) {
          options.onEvent(event);
          // 终态已到达，不等待服务端继续关闭连接，也不接收迟到的进度。
          if (event.type === "error" || event.type === "result") return;
        }
      }
    }
    buffer += decoder.decode();
    const tail = parseSseChunk(buffer);
    if (tail) options.onEvent(tail);
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

function parseSseChunk(chunk: string): AgentEvent | null {
  const payload = chunk
    .split("\n")
    .filter((line) => line.startsWith("data:"))
    .map((line) => line.replace(/^data:\s?/, ""))
    .join("\n")
    .trim();

  if (!payload) return null;

  try {
    return JSON.parse(payload) as AgentEvent;
  } catch {
    return {
      type: "error",
      message: `无法解析后端事件：${payload}`,
    };
  }
}
