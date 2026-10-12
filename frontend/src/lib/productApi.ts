/** 所有 HTTP 请求放在客户端模块，组件只调用业务方法。 */
import type { Conversation, ConversationDetail, Favorite, Feedback, FrequentQuestion, ModelInput, ModelProfile } from "../types/agent";
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api${path}`, { ...init, headers: { "Content-Type": "application/json", ...init.headers } });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((v: { msg: string }) => v.msg).join("；") : `请求失败：HTTP ${response.status}`);
  }
  return response.status === 204 ? undefined as T : response.json();
}
const json = (method: string, body: unknown): RequestInit => ({ method, body: JSON.stringify(body) });
export const api = {
  sessions: () => request<Conversation[]>("/sessions?days=30"),
  session: (id: string) => request<ConversationDetail>(`/sessions/${id}`),
  createSession: () => request<Conversation>("/sessions", { method: "POST" }),
  patchSession: (id: string, body: { title?: string; pinned?: boolean }) => request<Conversation>(`/sessions/${id}`, json("PATCH", body)),
  deleteSession: (id: string) => request<void>(`/sessions/${id}`, { method: "DELETE" }),
  favorites: () => request<Favorite[]>("/favorites"),
  favorite: (question: string) => request<Favorite>("/favorites", json("POST", { question })),
  deleteFavorite: (id: string) => request<void>(`/favorites/${id}`, { method: "DELETE" }),
  frequent: (threshold: number) => request<FrequentQuestion[]>(`/questions/frequent?threshold=${threshold}`),
  feedback: (message_id: string) => request<Feedback>("/feedbacks", json("POST", { message_id })),
  feedbacks: (params: URLSearchParams) => request<{ items: Feedback[]; total: number; page: number }>(`/feedbacks?${params}`),
  patchFeedback: (id: string, body: { status: Feedback["status"]; remark: string }) => request<Feedback>(`/feedbacks/${id}`, json("PATCH", body)),
  models: () => request<{ items: ModelProfile[]; selected_id: string }>("/models"),
  addModel: (body: ModelInput) => request<ModelProfile>("/models", json("POST", body)),
  testModel: (body: ModelInput) => request<{ ok: boolean; message: string }>("/models/test", json("POST", body)),
  selectModel: (model_id: string) => request<{ selected_id: string }>("/models/selection", json("PUT", { model_id })),
};
