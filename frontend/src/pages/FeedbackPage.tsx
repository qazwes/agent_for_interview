import { useEffect, useRef, useState } from "react";
import { MessageSquareWarning, Search } from "lucide-react";
import { api } from "../lib/productApi";
import { errorText, formatDate } from "../lib/format";
import { useProduct } from "../state/preferences";
import { Modal } from "../components/Modal";
import { ResultTable } from "../components/ResultTable";
import type { Feedback } from "../types/agent";
export function FeedbackPage() {
  const { notify } = useProduct();
  const [q, setQ] = useState(""); const [keyword, setKeyword] = useState("");
  const [status, setStatus] = useState("all"); const [page, setPage] = useState(1); const [size, setSize] = useState(10);
  const [items, setItems] = useState<Feedback[]>([]); const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false); const [error, setError] = useState(""); const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Feedback>(); const [saving, setSaving] = useState(false);
  const generation = useRef(0);
  useEffect(() => { const timer = setTimeout(() => { setKeyword(q); setPage(1); }, 250); return () => clearTimeout(timer); }, [q]);
  useEffect(() => {
    const request = ++generation.current; setLoading(true); setError("");
    api.feedbacks(new URLSearchParams({ q: keyword, status, page: String(page), page_size: String(size) })).then(result => {
      if (generation.current === request) { setItems(result.items); setTotal(result.total); setPage(result.page); }
    }).catch(e => { if (generation.current === request) setError(errorText(e)); }).finally(() => { if (generation.current === request) setLoading(false); });
    return () => { ++generation.current; };
  }, [keyword, status, page, size, revision]);
  const save = async () => {
    if (!editing) return; setSaving(true);
    try { await api.patchFeedback(editing.id, { status: editing.status, remark: editing.remark }); setEditing(undefined); setRevision(revision + 1); notify("反馈处理已保存"); }
    catch (e) { notify(errorText(e)); } finally { setSaving(false); }
  };
  const pages = Math.max(1, Math.ceil(total / size));
  return <div className="settings-page"><div className="breadcrumb">反馈管理<span>/</span>回复校对</div><section className="card feedback-card"><header className="feedback-heading"><h2><MessageSquareWarning size={18} />回复校对</h2><small>此列表为标注 AI 回复数据有误的反馈记录</small></header>
    <div className="feedback-filters"><div className="search-input"><Search size={16} /><input aria-label="搜索反馈问题" placeholder="搜索问题…" value={q} onChange={e => setQ(e.target.value)} /></div><select aria-label="反馈状态" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}><option value="all">全部状态</option><option value="pending">待处理</option><option value="resolved">已处理</option></select><button className="button small" disabled={loading} onClick={() => setRevision(revision + 1)}>刷新</button><span>共 <strong>{total}</strong> 条</span></div>
    {error && <div className="error-box" role="alert">{error}</div>}
    <div className="table-scroll"><table className="data-table"><thead><tr><th>序号</th><th>问题</th><th>反馈时间</th><th>状态</th><th>操作</th></tr></thead><tbody>{items.map((row, index) => <tr key={row.id}><td>{(page - 1) * size + index + 1}</td><td>{row.question}</td><td>{formatDate(row.created_at)}</td><td><span className={`status-tag ${row.status}`}>{row.status === "pending" ? "待处理" : "已处理"}</span></td><td><button className="button text small" onClick={() => setEditing({ ...row })}>处理</button></td></tr>)}{!items.length && <tr><td colSpan={5} className="empty-note">{loading ? "正在加载…" : "暂无反馈数据"}</td></tr>}</tbody></table></div>
    <div className="pagination"><span>共 {total} 条，每页</span><select aria-label="每页条数" value={size} onChange={e => { setSize(Number(e.target.value)); setPage(1); }}><option>5</option><option>10</option><option>20</option></select><span>条</span><div className="page-buttons"><button disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>上一页</button><span>{page} / {pages}</span><button disabled={page >= pages || loading} onClick={() => setPage(page + 1)}>下一页</button></div></div>
  </section>
    {editing && <Modal title="反馈处理" wide onClose={() => { if (!saving) setEditing(undefined); }} footer={<><button className="button" disabled={saving} onClick={() => setEditing(undefined)}>取消</button><button className="button primary" disabled={saving} onClick={() => void save()}>{saving ? "保存中…" : "确认"}</button></>}><div className="feedback-dialog"><div><h4>用户提问</h4><div className="feedback-question">{editing.question}</div><h4>AI回复</h4><div className="feedback-answer"><p>{editing.answer.content}</p><ResultTable rows={editing.answer.payload?.data || []} columns={editing.answer.payload?.presentation?.columns} /></div></div><div><label>处理状态<select value={editing.status} onChange={e => setEditing({ ...editing, status: e.target.value as Feedback["status"] })}><option value="pending">待处理</option><option value="resolved">已处理</option></select></label><label>处理备注<textarea placeholder="请填写处理备注…" maxLength={5000} value={editing.remark} onChange={e => setEditing({ ...editing, remark: e.target.value })} /></label></div></div></Modal>}
  </div>;
}
