/** React 状态负责即时渲染，localStorage 负责刷新后的保留。 */
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
export type Preferences = {
  greeting: boolean; greetingText: string; greetingQuestions: string[];
  suggestions: boolean; hotRecommend: boolean; hotThreshold: number; modelConfig: boolean;
};
export const defaults: Preferences = {
  greeting: true, greetingText: "欢迎使用智能AI问数，您可以向我咨询经营数据、报表分析相关问题。",
  greetingQuestions: ["统计2026年1至5月各产品线的收入和销量", "北京代表处2026年1至5月各产品线收入是多少？", "深圳代表处2026年1至5月各产品型号的销量和收入是多少？"],
  suggestions: true, hotRecommend: true, hotThreshold: 3, modelConfig: true,
};
const key = "my-agent.preferences.v1";
function load(): Preferences {
  try {
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    if (!saved) return defaults;
    return {
      greeting: typeof saved.greeting === "boolean" ? saved.greeting : defaults.greeting,
      greetingText: typeof saved.greetingText === "string" && saved.greetingText.trim() ? saved.greetingText : defaults.greetingText,
      greetingQuestions: Array.isArray(saved.greetingQuestions) ? saved.greetingQuestions.filter((q: unknown) => typeof q === "string").slice(0, 10) : defaults.greetingQuestions,
      suggestions: typeof saved.suggestions === "boolean" ? saved.suggestions : true,
      hotRecommend: typeof saved.hotRecommend === "boolean" ? saved.hotRecommend : true,
      hotThreshold: Number.isInteger(saved.hotThreshold) && saved.hotThreshold > 0 ? saved.hotThreshold : 3,
      modelConfig: typeof saved.modelConfig === "boolean" ? saved.modelConfig : true,
    };
  } catch { return defaults; }
}
type Context = { preferences: Preferences; savePreferences: (patch: Partial<Preferences>) => void; notify: (text: string) => void };
const ProductContext = createContext<Context | null>(null);
export function ProductProvider({ children }: { children: ReactNode }) {
  const [preferences, setPreferences] = useState(load);
  const [toast, setToast] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const notify = (text: string) => { clearTimeout(timer.current); setToast(text); timer.current = setTimeout(() => setToast(""), 4000); };
  useEffect(() => () => clearTimeout(timer.current), []);
  const savePreferences = (patch: Partial<Preferences>) => {
    const next = { ...preferences, ...patch };
    try { localStorage.setItem(key, JSON.stringify(next)); }
    catch { notify("浏览器无法保存配置，本次设置仅在当前页面有效。"); }
    setPreferences(next);
  };
  return <ProductContext.Provider value={{ preferences, savePreferences, notify }}>{children}{toast && <div className="toast" role="status">{toast}</div>}</ProductContext.Provider>;
}
export function useProduct() {
  const value = useContext(ProductContext);
  if (!value) throw new Error("缺少 ProductProvider");
  return value;
}
