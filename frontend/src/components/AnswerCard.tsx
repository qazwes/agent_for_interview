import { lazy, Suspense, useState } from "react";
import { Bot, ChevronRight, CircleCheck, CircleAlert, CircleMinus, LoaderCircle, Copy, Frown, ArrowRight } from "lucide-react";
import { ResultTable } from "./ResultTable";
const QueryChart = lazy(() => import("./QueryChart").then(module => ({ default: module.QueryChart })));
import { Modal } from "./Modal";
import { api } from "../lib/productApi";
import { copyText, errorText, formatDate, formatValue } from "../lib/format";
import { closeMessageProgress } from "../lib/queryProgress";
import { useProduct } from "../state/preferences";
import type { ChatMessage } from "../types/agent";
export function AnswerCard({ message, onAsk, disabled }: { message: ChatMessage; onAsk: (q: string) => void; disabled: boolean }) {
  const { preferences, notify } = useProduct();
  const [expanded, setExpanded] = useState(false);
  const [statKey, setStatKey] = useState("");
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const payload = closeMessageProgress(message).payload, presentation = payload?.presentation, rows = payload?.data || [];
  const stat = presentation?.statistics.find(s => s.key === statKey) || presentation?.statistics[0];
  const feedback = async () => {
    setSubmitting(true);
    try { await api.feedback(message.id); setFeedbackOpen(false); notify("反馈已提交，可在回复校对页面查看。"); }
    catch (e) { notify(errorText(e)); } finally { setSubmitting(false); }
  };
  const copy = async () => {
    const text = [message.content, presentation?.query, ...rows.map(row => Object.entries(row).map(([k, v]) => `${k}：${formatValue(v)}`).join("，"))].filter(Boolean).join("\n");
    try { await copyText(text); notify("已复制回答"); } catch { notify("复制失败，请检查浏览器剪贴板权限。"); }
  };
  return <article className="answer-card">
    <div className="answer-avatar"><Bot size={21} /></div>
    <button className="analysis-toggle" onClick={() => setExpanded(!expanded)} aria-expanded={expanded}><Bot size={16} />分析过程<ChevronRight size={15} className={expanded ? "expanded" : ""} /><small>{expanded ? "点击收起" : "点击展开"}</small></button>
    {expanded && <div className="analysis-content">
      {(payload?.steps || []).map(step => <div className={`analysis-step ${step.status}`} key={step.step}>{step.status === "running" ? <LoaderCircle className="spin" size={15} /> : step.status === "error" ? <CircleAlert size={15} /> : step.status === "cancelled" ? <CircleMinus size={15} /> : <CircleCheck size={15} />}<span>{step.step}{step.status === "cancelled" && "（已中断）"}</span></div>)}
      {presentation && <><p>实际使用的数据表：{presentation.tables.join("、") || "未解析"}</p>
        {Object.entries(presentation.data_dates || {}).map(([table, date]) => <p key={table}>{table} 最新数据日期：{date}</p>)}
        {presentation.metric_definitions.map((metric, i) => <p key={i}><strong>{metric.name}：</strong>{metric.description}</p>)}
        <p>实际执行 SQL：</p><pre>{presentation.sql}</pre>
      </>}
    </div>}
    {message.status === "streaming" && <p className="running-note"><LoaderCircle size={16} className="spin" />{message.content}</p>}
    {payload?.error && <div className="error-box" role="alert">{payload.error}</div>}
    {message.status === "error" && !payload?.error && <div className="error-box" role="alert">{message.content}</div>}
    {message.status === "cancelled" && <p className="empty-note">{message.content}</p>}
    {message.status === "done" && <>
      <section className="answer-module"><h3><span>1</span>数据发现</h3><div className="module-content">
        <p>{message.content}</p>{presentation && <>
          <p>问题：{presentation.query}</p>
          {presentation.conditions.length > 0 && <p>查询条件：<code>{presentation.conditions.join("；")}</code></p>}
          {presentation.statistics.filter(s => s.total !== null).map(s => <p key={s.key}>{s.label}合计：<strong>{formatValue(s.total)} {s.unit}</strong></p>)}
          <small className="muted">{presentation.result_scope}</small>
        </>}
      </div></section>
      <section className="answer-module"><h3><span>2</span>数据表格</h3><ResultTable rows={rows} columns={presentation?.columns} /></section>
      <section className="answer-module"><h3><span>3</span>数据统计</h3><div className="module-content">
        <p>总记录数：{rows.length} 条</p>
        {presentation && presentation.statistics.length > 1 && <label className="stat-selector">统计指标<select value={stat?.key || ""} onChange={e => setStatKey(e.target.value)}>{presentation.statistics.map(s => <option value={s.key} key={s.key}>{s.label}</option>)}</select></label>}
        {stat ? <div className="statistics-grid">{[["平均值", stat.average], ["最大值", stat.max], ["最小值", stat.min]].map(([name, value]) => <div key={String(name)}><small>{name}</small><strong>{formatValue(value)} <span>{stat.unit}</span></strong></div>)}</div> : <p className="muted">没有可统计的数值指标。</p>}
        {stat?.total === null && <small className="muted">此指标不计算合计，平均值为返回记录的算术平均值。</small>}
      </div></section>
      <section className="answer-module"><h3><span>4</span>数据可视化</h3>{presentation ? <Suspense fallback={<p className="empty-note">正在加载图表…</p>}><QueryChart rows={rows} presentation={presentation} /></Suspense> : <p className="empty-note">本条历史记录没有图表配置。</p>}</section>
    </>}
    <footer className="answer-footer"><div className="message-actions"><button className="icon-button" aria-label="复制回答" onClick={() => void copy()}><Copy size={16} /></button>{message.status === "done" && <button className="icon-button" aria-label="反馈回答" onClick={() => setFeedbackOpen(true)}><Frown size={16} /></button>}</div><small>{payload?.elapsed_ms !== undefined && `耗时 ${(payload.elapsed_ms / 1000).toFixed(1)}s · `}{payload?.model_name && `${payload.model_name} · `}{formatDate(message.created_at)}</small></footer>
    {message.status === "done" && preferences.suggestions && !!presentation?.suggestions.length && <div className="followups">{presentation.suggestions.map((q, index) => <button key={q} disabled={disabled} onClick={() => onAsk(q)} title={q}>{["查看相关明细", "比较最高与最低值", "按产品线展开"][index] || q}<ArrowRight size={13} /></button>)}</div>}
    {feedbackOpen && <Modal title="AI回复反馈" onClose={() => { if (!submitting) setFeedbackOpen(false); }} footer={<button className="button" disabled={submitting} onClick={() => setFeedbackOpen(false)}>取消</button>}><p>请问你是对哪里不满意呢？</p><button className="button full-width" disabled={submitting} onClick={() => void feedback()}><CircleAlert size={16} />{submitting ? "提交中…" : "数据有误，提交反馈"}</button></Modal>}
  </article>;
}
