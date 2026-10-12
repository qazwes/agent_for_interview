import { useState } from "react";
import { ChevronLeft, MoreHorizontal, Pin, Plus, Pencil, Trash2 } from "lucide-react";
import { Modal } from "./Modal";
import { errorText } from "../lib/format";
import { useProduct } from "../state/preferences";
import type { Conversation } from "../types/agent";
export function ConversationSidebar({ sessions, activeId, disabled, onClose, onNew, onSelect, onPatch, onDelete }: {
  sessions: Conversation[]; activeId?: string; disabled: boolean; onClose: () => void;
  onNew: () => void; onSelect: (id: string) => void;
  onPatch: (id: string, patch: { title?: string; pinned?: boolean }) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const { notify } = useProduct();
  const [menu, setMenu] = useState<string>();
  const [dialog, setDialog] = useState<{ kind: "rename" | "delete"; row: Conversation }>();
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const confirm = async () => {
    if (!dialog) return;
    setBusy(true);
    try {
      if (dialog.kind === "rename") await onPatch(dialog.row.id, { title: title.trim() });
      else await onDelete(dialog.row.id);
      setDialog(undefined); notify("操作已完成");
    } catch (e) { notify(errorText(e)); } finally { setBusy(false); }
  };
  return <aside className="conversation-sidebar">
    <header><button className="icon-button" aria-label="收起历史记录" onClick={onClose}><ChevronLeft size={18} /></button><span>近30天记录</span></header>
    <button className="new-chat" disabled={disabled} onClick={onNew}><Plus size={17} />开启新对话</button>
    <div className="conversation-list">{sessions.length === 0 && <p className="empty-note">暂无历史记录</p>}{sessions.map(row => <div className={`conversation-item ${row.id === activeId ? "active" : ""}`} key={row.id}>
      <button className="conversation-title" title={row.title} disabled={disabled} onClick={() => onSelect(row.id)}>{row.pinned && <Pin size={12} />}<span>{row.title}</span></button>
      <button className="icon-button" disabled={disabled} aria-label={`操作会话：${row.title}`} onClick={() => setMenu(menu === row.id ? undefined : row.id)}><MoreHorizontal size={16} /></button>
      {menu === row.id && <><button className="menu-backdrop" aria-label="关闭会话菜单" onClick={() => setMenu(undefined)} /><div className="conversation-menu">
        <button onClick={() => { setMenu(undefined); void onPatch(row.id, { pinned: !row.pinned }).catch(e => notify(errorText(e))); }}><Pin size={14} />{row.pinned ? "取消置顶" : "置顶"}</button>
        <button onClick={() => { setMenu(undefined); setTitle(row.title); setDialog({ kind: "rename", row }); }}><Pencil size={14} />重命名</button>
        <button className="danger-text" onClick={() => { setMenu(undefined); setDialog({ kind: "delete", row }); }}><Trash2 size={14} />删除</button>
      </div></>}
    </div>)}</div>
    {dialog && <Modal title={dialog.kind === "rename" ? "重命名会话" : "删除会话"} onClose={() => { if (!busy) setDialog(undefined); }} footer={<><button className="button" disabled={busy} onClick={() => setDialog(undefined)}>取消</button><button className={`button ${dialog.kind === "delete" ? "danger" : "primary"}`} disabled={busy || (dialog.kind === "rename" && !title.trim())} onClick={() => void confirm()}>{busy ? "处理中…" : "确认"}</button></>}>
      {dialog.kind === "rename" ? <label>会话标题<input autoFocus maxLength={100} value={title} onChange={e => setTitle(e.target.value)} /></label> : <p>确定删除「{dialog.row.title}」及其消息吗？</p>}
    </Modal>}
  </aside>;
}
