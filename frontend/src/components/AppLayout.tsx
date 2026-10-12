import { useState, type ReactNode } from "react";
import { Bot, ChartNoAxesCombined, ChevronDown, ChevronLeft, Settings, SlidersHorizontal, Flag, MessageSquareWarning } from "lucide-react";
export type Page = "chat" | "app" | "models" | "feedbacks";
export function AppLayout({ page, children }: { page: Page; children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const [systemOpen, setSystemOpen] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(true);
  return <div className="app-layout">
    <header className="topbar"><div className="brand"><ChartNoAxesCombined size={21} />AI问数</div><span className="version">v1.0.0</span></header>
    <div className="app-body"><aside className={`main-sidebar${collapsed ? " collapsed" : ""}`}>
      <nav aria-label="主导航">
        <a href="#/chat" title="智能问数" className={`nav-item ${page === "chat" ? "active" : ""}`}><Bot size={19} /><span>智能问数</span></a>
        <button className="nav-item" title="系统管理" aria-expanded={systemOpen} onClick={() => { if (collapsed) setCollapsed(false); setSystemOpen(!systemOpen); }}><Settings size={18} /><span>系统管理</span><ChevronDown className={systemOpen ? "" : "rotated"} size={15} /></button>
        {!collapsed && systemOpen && <a href="#/settings/app" className={`nav-item sub ${page === "app" || page === "models" ? "active" : ""}`}><SlidersHorizontal size={17} /><span>应用配置</span></a>}
        <button className="nav-item" title="反馈管理" aria-expanded={feedbackOpen} onClick={() => { if (collapsed) setCollapsed(false); setFeedbackOpen(!feedbackOpen); }}><Flag size={18} /><span>反馈管理</span><ChevronDown className={feedbackOpen ? "" : "rotated"} size={15} /></button>
        {!collapsed && feedbackOpen && <a href="#/feedbacks" className={`nav-item sub ${page === "feedbacks" ? "active" : ""}`}><MessageSquareWarning size={17} /><span>回复校对</span></a>}
      </nav><button className="sidebar-toggle" aria-label={collapsed ? "展开导航" : "收起导航"} onClick={() => setCollapsed(!collapsed)}><ChevronLeft size={19} className={collapsed ? "flipped" : ""} /></button>
    </aside><main className={`page-main ${page === "chat" ? "chat-main" : ""}`}>{children}</main></div>
  </div>;
}
