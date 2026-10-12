import type { ChatMessage } from "../types/agent";

/** 终态消息不允许残留 running；同时兼容旧版服务与已有历史记录。 */
export function closeMessageProgress(message: ChatMessage): ChatMessage {
  if (message.status === "streaming" || !message.payload?.steps) return message;
  return {
    ...message,
    payload: {
      ...message.payload,
      steps: message.payload.steps.map(step => step.status === "running" ? { ...step, status: "cancelled" } : step),
    },
  };
}
