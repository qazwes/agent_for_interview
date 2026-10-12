import { useEffect, useRef, useState } from "react";
import { ArrowUp, Copy, PanelLeft, Pencil, RotateCw, Star, Zap, X, Square } from "lucide-react";
import { useChat } from "../hooks/useChat";
import { useProduct } from "../state/preferences";
import { ConversationSidebar } from "../components/ConversationSidebar";
import { AnswerCard } from "../components/AnswerCard";
import { copyText } from "../lib/format";
export function ChatPage() {
  const chat = useChat();
  const { preferences, notify } = useProduct();
  const [draft, setDraft] = useState("");
  const [sidebar, setSidebar] = useState(() => { try { return localStorage.getItem("my-agent.history-open") === "1"; } catch { return false; } });
  const [quick, setQuick] = useState(false);
  const [quickTab, setQuickTab] = useState<"frequent" | "favorite">("frequent");
  const [editing, setEditing] = useState<{ id: string; text: string }>();
  const scroll = useRef<HTMLDivElement>(null);
  const disabled = chat.streaming || chat.loading;
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: "smooth" }); }, [chat.messages]);
  const toggleSidebar = () => { setSidebar(!sidebar); try { localStorage.setItem("my-agent.history-open", sidebar ? "0" : "1"); } catch { /* ignore */ } };
  const send = (question = draft, source?: string) => {
    if (disabled || !question.trim()) return;
    setDraft(""); setQuick(false); setEditing(undefined); void chat.submit(question, source);
  };
  const title = chat.sessions.find(s => s.id === chat.sessionId)?.title || "AI 智能问数对话";
  return <div className="chat-page">
    {sidebar && <ConversationSidebar sessions={chat.sessions} activeId={chat.sessionId} disabled={disabled} onClose={toggleSidebar} onNew={() => { setDraft(""); setEditing(undefined); void chat.newSession(); }} onSelect={id => { setDraft(""); setEditing(undefined); void chat.loadSession(id); }} onPatch={chat.patchSession} onDelete={chat.deleteSession} />}
    <div className="chat-workspace"><header className="chat-header"><button className="icon-button" aria-label="展开或收起历史记录" onClick={toggleSidebar}><PanelLeft size={19} /></button><span>{title}</span><button className="button small" disabled={disabled} onClick={() => { setDraft(""); void chat.newSession(); }}>新对话</button></header>
      {chat.error && <div className="error-box" role="alert">{chat.error}<button className="button small" onClick={() => void chat.reload()}>重试加载</button></div>}
      <div className="chat-scroll" ref={scroll}>
        {chat.loading && !chat.messages.length ? <p className="empty-note">正在加载会话…</p> : !chat.messages.length ? <div className="welcome"><div><h1>你好</h1><h2>我是 AI 问数助手</h2>{preferences.greeting && <><p>{preferences.greetingText}</p>{preferences.greetingQuestions.length > 0 && <><h4>你可以这么问我</h4><div className="greeting-questions">{preferences.greetingQuestions.map((q, i) => <button key={i} disabled={disabled} onClick={() => send(q)}>{q}</button>)}</div></>}</>}</div></div> : <div className="message-list">{chat.messages.map(message => message.role === "assistant" ? <AnswerCard key={message.id} message={message} onAsk={send} disabled={disabled} /> : <article className="user-message" key={message.id}>
          <div className="user-bubble">{editing?.id === message.id ? <><textarea aria-label="编辑问题" autoFocus value={editing.text} maxLength={4000} onChange={e => setEditing({ ...editing, text: e.target.value })} /><div className="edit-actions"><button className="button small" onClick={() => setEditing(undefined)}>取消</button><button className="button primary small" disabled={disabled || !editing.text.trim()} onClick={() => send(editing.text, message.id)}>重新发送</button></div></> : message.content}</div>
          {editing?.id !== message.id && <div className="message-actions"><button className={`icon-button ${chat.favorites.some(f => f.question === message.content) ? "favorited" : ""}`} aria-label="收藏问题" onClick={() => void chat.toggleFavorite(message.content)}><Star size={15} /></button><button className="icon-button" disabled={disabled} aria-label="编辑问题" onClick={() => setEditing({ id: message.id, text: message.content })}><Pencil size={15} /></button><button className="icon-button" disabled={disabled} aria-label="重新发送问题" onClick={() => send(message.content, message.id)}><RotateCw size={15} /></button><button className="icon-button" aria-label="复制问题" onClick={() => void copyText(message.content).then(() => notify("已复制问题")).catch(() => notify("复制失败，请检查浏览器权限。"))}><Copy size={15} /></button></div>}
        </article>)}</div>}
      </div>
      <div className="composer-area">{quick && <><button className="quick-backdrop" aria-label="关闭快捷提问" onClick={() => setQuick(false)} /><div className="quick-panel"><header><strong><Zap size={16} />快捷提问</strong><button className="icon-button" aria-label="关闭快捷提问" onClick={() => setQuick(false)}><X size={16} /></button></header><div className="quick-tabs"><button className={quickTab === "frequent" ? "active" : ""} onClick={() => setQuickTab("frequent")}>常问</button><button className={quickTab === "favorite" ? "active" : ""} onClick={() => setQuickTab("favorite")}>收藏</button></div><div className="quick-list">
        {quickTab === "frequent" ? chat.frequent.length ? chat.frequent.map(row => <button disabled={disabled} key={row.question} onClick={() => send(row.question)}>{row.question}<small>{row.count} 次</small></button>) : <p className="empty-note">{preferences.hotRecommend ? "暂无达到频次阈值的问题" : "常问功能已关闭"}</p> : chat.favorites.length ? chat.favorites.map(row => <div key={row.id}><button disabled={disabled} onClick={() => send(row.question)}>{row.question}</button><button className="icon-button" aria-label="取消收藏" onClick={() => void chat.toggleFavorite(row.question)}><X size={14} /></button></div>) : <p className="empty-note">暂无收藏问题</p>}
      </div></div></>}
        <form className="query-composer" onSubmit={e => { e.preventDefault(); send(); }}><button type="button" className="icon-button" aria-label="快捷提问" onClick={() => { setQuickTab("frequent"); setQuick(!quick); }}><Zap size={20} /></button><textarea  aria-label="问题输入框" placeholder="请写下您的想法…" value={draft} maxLength={4000} disabled={disabled} onChange={e => setDraft(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }} />{chat.streaming ? <button type="button" className="send-button stop" aria-label="停止查询" onClick={chat.stop}><Square size={16} /></button> : <button className="send-button" aria-label="发送问题" disabled={disabled || !draft.trim()}><ArrowUp size={20} /></button>}</form>
      </div>
    </div>
  </div>;
}
