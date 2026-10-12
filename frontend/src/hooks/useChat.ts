/** 会话业务状态：组件不用处理 fetch、SSE 或消息持久化细节。 */
import { useEffect, useRef, useState } from "react";
import { api } from "../lib/productApi";
import { streamQuery } from "../lib/agentApi";
import { errorText } from "../lib/format";
import { closeMessageProgress } from "../lib/queryProgress";
import { useProduct } from "../state/preferences";
import type { ChatMessage, Conversation, Favorite, FrequentQuestion, MessagePayload } from "../types/agent";

export function useChat() {
  const { notify, preferences } = useProduct();
  const [sessions, setSessions] = useState<Conversation[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>();
  const [favorites, setFavorites] = useState<Favorite[]>([]);
  const [frequent, setFrequent] = useState<FrequentQuestion[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const selection = useRef(0);
  const activeId = useRef<string | undefined>(undefined);
  const refreshSessions = async () => { setSessions(await api.sessions()); };
  const activate = (id: string) => {
    setSessionId(id); activeId.current = id;
    try { localStorage.setItem("my-agent.active-session", id); } catch { /* 当前会话仍可使用 */ }
  };
  const loadSession = async (id: string) => {
    if (controller.current) return;
    const request = ++selection.current;
    setLoading(true); setError("");
    try {
      const detail = await api.session(id);
      if (request === selection.current) { activate(id); setMessages(detail.messages.map(closeMessageProgress)); }
    } catch (e) { if (request === selection.current) setError(errorText(e)); }
    finally { if (request === selection.current) setLoading(false); }
  };
  const reload = async () => {
    setLoading(true); setError("");
    try { await refreshSessions(); if (activeId.current) await loadSession(activeId.current); }
    catch (e) { setError(errorText(e)); }
    finally { setLoading(false); }
  };
  useEffect(() => {
    let alive = true;
    const initialize = async () => {
      try {
        const [list, fav] = await Promise.all([api.sessions(), api.favorites()]);
        if (!alive) return;
        setSessions(list); setFavorites(fav);
        let saved: string | null = null;
        try { saved = localStorage.getItem("my-agent.active-session"); } catch { /* 无本地存储 */ }
        const chosen = list.find(s => s.id === saved);
        if (chosen) {
          const detail = await api.session(chosen.id);
          if (alive) { activate(chosen.id); setMessages(detail.messages.map(closeMessageProgress)); }
        }
      } catch (e) { if (alive) setError(errorText(e)); }
      finally { if (alive) setLoading(false); }
    };
    void initialize();
    return () => { alive = false; controller.current?.abort(); };
  }, []);
  useEffect(() => {
    let alive = true;
    if (preferences.hotRecommend) api.frequent(preferences.hotThreshold).then(rows => { if (alive) setFrequent(rows); }).catch(() => { if (alive) setFrequent([]); });
    else setFrequent([]);
    return () => { alive = false; };
  }, [preferences.hotThreshold, preferences.hotRecommend]);
  const newSession = async () => {
    if (controller.current || loading) return;
    setLoading(true);
    try {
      const row = await api.createSession(); ++selection.current;
      activate(row.id); setMessages([]); setError(""); await refreshSessions();
    } catch (e) { notify(errorText(e)); }
    finally { setLoading(false); }
  };
  const patchSession = async (id: string, patch: { title?: string; pinned?: boolean }) => {
    await api.patchSession(id, patch); await refreshSessions();
  };
  const deleteSession = async (id: string) => {
    await api.deleteSession(id);
    if (activeId.current === id) {
      ++selection.current; activeId.current = undefined; setSessionId(undefined); setMessages([]);
      try { localStorage.removeItem("my-agent.active-session"); } catch { /* ignore */ }
    }
    await refreshSessions();
  };
  const toggleFavorite = async (question: string) => {
    try {
      const existing = favorites.find(f => f.question === question);
      if (existing) await api.deleteFavorite(existing.id); else await api.favorite(question);
      setFavorites(await api.favorites()); notify(existing ? "已取消收藏" : "问题已收藏");
    } catch (e) { notify(errorText(e)); }
  };
  const submit = async (raw: string, sourceMessageId?: string) => {
    const question = raw.trim();
    if (!question || controller.current || loading) return false;
    const abort = new AbortController(); controller.current = abort; setStreaming(true); setError("");
    const temporaryUser = crypto.randomUUID(), temporaryAnswer = crypto.randomUUID();
    let answerId: string = temporaryAnswer;
    let terminal = false;
    const timestamp = new Date().toISOString();
    const base = { session_id: activeId.current || "", created_at: timestamp, payload: null };
    setMessages(current => [...current,
      { ...base, id: temporaryUser, role: "user", content: question, status: "done" },
      { ...base, id: temporaryAnswer, role: "assistant", content: "正在连接问数服务…", status: "streaming", reply_to_id: temporaryUser },
    ]);
    const patch = (update: (m: ChatMessage) => ChatMessage) => setMessages(current => current.map(m => m.id === answerId ? closeMessageProgress(update(m)) : m));
    try {
      await streamQuery(question, {
        sessionId: activeId.current, sourceMessageId, signal: abort.signal,
        onEvent: event => {
          if (terminal) return;
          if (event.type === "conversation") {
            activate(event.session_id); answerId = event.assistant.id;
            setMessages(current => current.map(m => m.id === temporaryUser ? event.user : m.id === temporaryAnswer ? event.assistant : m));
          } else if (event.type === "progress") {
            patch(m => ({ ...m, content: event.status === "running" ? `正在执行：${event.step}` : m.content,
              payload: { ...m.payload, steps: [...(m.payload?.steps || []).filter(s => s.step !== event.step), { step: event.step, status: event.status }] } }));
          } else if (event.type === "result") {
            terminal = true;
            patch(m => ({ ...m, status: "done", content: event.data.length ? `查询完成，共 ${event.data.length} 条结果。` : "查询完成，当前条件下没有数据。",
              payload: { ...m.payload, ...event } as MessagePayload }));
          } else {
            terminal = true;
            patch(m => ({ ...m, status: "error", content: "查询失败。", payload: { ...m.payload, error: event.message } }));
          }
        },
      });
      if (!terminal) throw new Error("连接已结束，但没有收到查询结果。请重试。");
    } catch (e) {
      const cancelled = abort.signal.aborted;
      if (!terminal) patch(m => ({ ...m, status: cancelled ? "cancelled" : "error", content: cancelled ? "已停止本次查询。" : "查询失败。",
        payload: { ...m.payload, error: cancelled ? undefined : errorText(e) } }));
    } finally {
      controller.current = null; setStreaming(false);
      await refreshSessions().catch(e => notify(errorText(e)));
      if (preferences.hotRecommend) await api.frequent(preferences.hotThreshold).then(setFrequent).catch(() => {});
    }
    return true;
  };
  return { sessions, messages, sessionId, favorites, frequent, streaming, loading, error, reload,
    loadSession, newSession, patchSession, deleteSession, toggleFavorite, submit,
    stop: () => controller.current?.abort() };
}
