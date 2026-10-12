import { useState } from "react";
import { MessageSquare, List, Box, Flame, Settings, Plus, X } from "lucide-react";
import { useProduct } from "../state/preferences";
import { Modal } from "../components/Modal";
export function AppConfigPage() {
  const { preferences: p, savePreferences, notify } = useProduct();
  const [dialog, setDialog] = useState<"greeting" | "hot">();
  const [text, setText] = useState(""); const [questions, setQuestions] = useState<string[]>([]); const [threshold, setThreshold] = useState("3");
  const save = () => {
    if (dialog === "greeting") {
      if (!text.trim()) { notify("开场白不能为空"); return; }
      savePreferences({ greetingText: text.trim(), greetingQuestions: questions.map(q => q.trim()).filter(Boolean) });
    } else {
      const value = Number(threshold);
      if (!Number.isInteger(value) || value < 1 || value > 100000) { notify("频次阈值必须是 1 至 100000 的整数"); return; }
      savePreferences({ hotThreshold: value });
    }
    setDialog(undefined); notify("配置已保存");
  };
  const cards = [
    { key: "greeting" as const, title: "对话开场白", Icon: MessageSquare, description: "开启后，新对话显示开场白和开场问题。", configure: () => { setText(p.greetingText); setQuestions([...p.greetingQuestions]); setDialog("greeting"); } },
    { key: "suggestions" as const, title: "下一步问题建议", Icon: List, description: "开启后，回答下方显示相关延伸问题，点击后继续问数。" },
    { key: "modelConfig" as const, title: "模型配置", Icon: Box, description: "配置智能问数使用的 AI 模型。开关控制配置入口显示。", configure: () => { window.location.hash = "/settings/models"; } },
    { key: "hotRecommend" as const, title: "常问设置", Icon: Flame, description: "提问次数超过设置阈值的问题，会出现在快捷提问的常问列表。", configure: () => { setThreshold(String(p.hotThreshold)); setDialog("hot"); } },
  ];
  return <div className="settings-page"><div className="breadcrumb">系统管理 <span>/</span> 应用配置</div><section className="card"><div className="settings-grid">{cards.map(({ key, title, Icon, description, configure }) => <article className="setting-card" key={key}><header><div className={`setting-icon ${key}`}><Icon size={21} /></div><strong>{title}</strong><div className="setting-actions">{configure && <button className="icon-button" aria-label={`配置${title}`} disabled={key === "modelConfig" && !p.modelConfig} onClick={configure}><Settings size={17} /></button>}<button role="switch" aria-checked={p[key]} aria-label={title} className={`switch ${p[key] ? "on" : ""}`} onClick={() => savePreferences({ [key]: !p[key] })} /></div></header><p>{description}</p></article>)}</div></section>
    {dialog && <Modal title={dialog === "greeting" ? "对话开场白" : "常问设置"} onClose={() => setDialog(undefined)} footer={<><button className="button" onClick={() => setDialog(undefined)}>取消</button><button className="button primary" onClick={save}>保存</button></>}>
      {dialog === "greeting" ? <><label>开场白文案<textarea value={text} maxLength={1000} onChange={e => setText(e.target.value)} /></label><div className="form-section-heading"><strong>开场问题 · {questions.length}/10</strong><button className="button text small" disabled={questions.length >= 10} onClick={() => setQuestions([...questions, ""])}><Plus size={15} />添加开场问题</button></div>{questions.map((q, i) => <div className="question-input-row" key={i}><input aria-label={`开场问题${i + 1}`} value={q} maxLength={100} placeholder="请输入快捷问题" onChange={e => setQuestions(questions.map((v, j) => j === i ? e.target.value : v))} /><button className="icon-button" aria-label={`删除开场问题${i + 1}`} onClick={() => setQuestions(questions.filter((_, j) => j !== i))}><X size={17} /></button></div>)}</> : <label>问题频次阈值<input type="number" min={1} max={100000} value={threshold} onChange={e => setThreshold(e.target.value)} /><small className="muted">同一问题的提问次数超过此值时，列为常问。</small></label>}
    </Modal>}
  </div>;
}
