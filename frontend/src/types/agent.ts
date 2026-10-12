export type Row = Record<string, unknown>;
export type StepState = { step: string; status: "running" | "success" | "error" | "cancelled" };
export type ResultColumn = { key: string; label: string; kind: "dimension" | "metric"; unit: string; additive: boolean };
export type Statistic = { key: string; label: string; unit: string; count: number; total: number | null; average: number; max: number; min: number };
export type Presentation = {
  query: string; sql: string; tables: string[]; conditions: string[];
  metric_definitions: Array<{ name: string; description: string }>;
  columns: ResultColumn[]; statistics: Statistic[]; row_count: number; result_scope: string;
  data_dates: Record<string, string>; suggestions: string[];
  chart: { type: "bar" | "line" | "pie"; dimension: string; metrics: string[] } | null;
};
export type ResultEvent = { type: "result"; data: Row[]; presentation?: Presentation; elapsed_ms?: number; model_name?: string; message_id?: string };
export type MessagePayload = Partial<ResultEvent> & { steps?: StepState[]; error?: string };
export type ChatMessage = {
  id: string; session_id: string; role: "user" | "assistant"; content: string;
  status: "streaming" | "done" | "error" | "cancelled";
  reply_to_id?: string; source_message_id?: string; created_at: string; payload: MessagePayload | null;
};
export type Conversation = { id: string; title: string; pinned: boolean; created_at: string; updated_at: string };
export type ConversationDetail = Conversation & { messages: ChatMessage[] };
export type AgentEvent =
  | ({ type: "progress" } & StepState)
  | ResultEvent
  | { type: "error"; message: string }
  | { type: "conversation"; session_id: string; user: ChatMessage; assistant: ChatMessage };
export type Favorite = { id: string; question: string };
export type FrequentQuestion = { question: string; count: number };
export type ModelProfile = { id: string; name: string; model_name: string; base_url: string };
export type ModelInput = { name: string; model_name: string; base_url: string; api_key: string };
export type Feedback = {
  id: string; message_id: string | null; question: string; status: "pending" | "resolved";
  remark: string; created_at: string; answer: { content: string; payload: MessagePayload };
};
