import { useEffect, useState } from "react";
import { Box, Plug, Save } from "lucide-react";
import { api } from "../lib/productApi";
import { errorText } from "../lib/format";
import { useProduct } from "../state/preferences";
import { Modal } from "../components/Modal";
import type { ModelInput, ModelProfile } from "../types/agent";
const emptyModel: ModelInput = { name: "", base_url: "", api_key: "", model_name: "" };
export function ModelConfigPage() {
  const { notify, preferences } = useProduct();
  const [models, setModels] = useState<ModelProfile[]>([]);
  const [selected, setSelected] = useState("env");
  const [saved, setSaved] = useState("env");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(emptyModel);
  const [tested, setTested] = useState(false);
  const [testMessage, setTestMessage] = useState("");
  const [busy, setBusy] = useState<"test" | "add" | "save">();
  const load = async () => {
    setLoading(true);
    try { const result = await api.models(); setModels(result.items); setSelected(result.selected_id); setSaved(result.selected_id); setError(""); }
    catch (e) { setError(errorText(e)); } finally { setLoading(false); }
  };
  useEffect(() => { void load(); }, []);
  const test = async () => {
    setBusy("test"); setTested(false); setTestMessage("正在测试连接…");
    try { const result = await api.testModel(form); setTested(result.ok); setTestMessage(result.message); }
    catch (e) { setTestMessage(errorText(e)); } finally { setBusy(undefined); }
  };
  const add = async () => {
    if (!tested) return;
    setBusy("add");
    try { const result = await api.addModel(form); setModels(current => [...current, result]); setSelected(result.id); setAdding(false); setForm(emptyModel); notify("模型已添加，请保存配置以切换问数模型。"); }
    catch (e) { notify(errorText(e)); } finally { setBusy(undefined); }
  };
  const save = async () => {
    setBusy("save");
    try { await api.selectModel(selected); setSaved(selected); notify("模型配置已保存，下次查询开始生效。"); }
    catch (e) { notify(errorText(e)); } finally { setBusy(undefined); }
  };
  const full = Object.values(form).every(v => v.trim());
  return <div className="settings-page"><div className="breadcrumb"><a href="#/settings/app">系统管理 / 应用配置</a><span>/</span>模型配置</div><section className="card model-settings"><h2><Box size={20} />应用模型设置</h2><p className="muted">选择 AI 问答使用的 LLM 模型</p>
    {!preferences.modelConfig ? <p className="empty-note">模型配置入口已关闭，请在应用配置中开启。</p> : <>
      {error && <div className="error-box">{error}<button className="button small" onClick={() => void load()}>重试</button></div>}
      <div className="model-setting-card"><label><strong>智能问数模型</strong><select aria-label="智能问数模型" value={selected} disabled={loading || !!busy} onChange={e => { if (e.target.value === "__add__") { setForm(emptyModel); setTested(false); setTestMessage(""); setAdding(true); } else setSelected(e.target.value); }}>{models.map(m => <option value={m.id} key={m.id}>{m.name}</option>)}<option value="__add__">── 新增模型 ──</option></select></label><p>用于智能问数、经营指标问答、台账数据分析</p></div>
      <div className="model-actions"><button className="button" disabled={loading || !!busy || selected === saved} onClick={() => void save()}><Save size={16} />{busy === "save" ? "保存中…" : "保存配置"}</button></div>
    </>}
  </section>
    {adding && <Modal title="新增模型" onClose={() => { if (!busy) { setAdding(false); setForm(emptyModel); } }} footer={<><button className="button" disabled={!full || !!busy} onClick={() => void test()}><Plug size={16} />{busy === "test" ? "测试中…" : "测试连接"}</button><div className="button-group"><button className="button" disabled={!!busy} onClick={() => { setAdding(false); setForm(emptyModel); }}>取消</button><button className="button primary" disabled={!tested || !!busy} onClick={() => void add()}>{busy === "add" ? "添加中…" : "添加"}</button></div></>}>
      {([ ["name", "显示名称", "例如：DeepSeek 问数模型"], ["base_url", "Base URL", "https://服务地址/v1"], ["api_key", "API Key", "输入模型服务密钥"], ["model_name", "Model Name", "输入服务支持的模型 ID"] ] as const).map(([key, label, placeholder]) => <label key={key}>{label}<input type={key === "api_key" ? "password" : "text"} autoComplete="off" disabled={!!busy} value={form[key]} placeholder={placeholder} onChange={e => { setForm({ ...form, [key]: e.target.value }); setTested(false); setTestMessage(""); }} /></label>)}
      {testMessage && <p role="status" className={tested ? "success-text" : "muted"}>{testMessage}</p>}
    </Modal>}
  </div>;
}
