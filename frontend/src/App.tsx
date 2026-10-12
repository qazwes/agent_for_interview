/** 应用入口只组装布局和页面；业务状态、请求、配置分别放在独立模块。 */
import { useEffect, useState } from "react";
import { AppLayout, type Page } from "./components/AppLayout";
import { ChatPage } from "./pages/ChatPage";
import { AppConfigPage } from "./pages/AppConfigPage";
import { ModelConfigPage } from "./pages/ModelConfigPage";
import { FeedbackPage } from "./pages/FeedbackPage";
import { ProductProvider } from "./state/preferences";
function currentPage(): Page {
  return ({ "#/settings/app": "app", "#/settings/models": "models", "#/feedbacks": "feedbacks" } as Record<string, Page>)[window.location.hash] || "chat";
}
export default function App() {
  const [page, setPage] = useState(currentPage);
  useEffect(() => { const update = () => setPage(currentPage()); window.addEventListener("hashchange", update); return () => window.removeEventListener("hashchange", update); }, []);
  return <ProductProvider><AppLayout page={page}>
    {/* 保持问数页挂载，切换配置页面时不会丢失正在接收的 SSE。 */}
    <div className="chat-page-host" hidden={page !== "chat"}><ChatPage /></div>
    {page === "app" && <AppConfigPage />}{page === "models" && <ModelConfigPage />}{page === "feedbacks" && <FeedbackPage />}
  </AppLayout></ProductProvider>;
}
