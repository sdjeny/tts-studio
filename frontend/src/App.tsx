import { useState } from "react";
import ProjectList from "./pages/ProjectList";
import ProjectDetail from "./pages/ProjectDetail";
import SettingsPage from "./pages/SettingsPage";

type Page = "home" | "project" | "settings";

export default function App() {
  const [page, setPage] = useState<Page>("home");
  const [projectId, setProjectId] = useState<string | null>(null);

  return (
    <div style={{ minHeight: "100vh", background: "#0f1117", color: "#e2e8f0" }}>
      <header
        style={{
          padding: "12px 24px",
          borderBottom: "1px solid #1e293b",
          display: "flex",
          alignItems: "center",
          gap: 12,
          background: "#1a1d27",
        }}
      >
        <span
          style={{ cursor: "pointer", fontWeight: 700, fontSize: 18 }}
          onClick={() => { setPage("home"); setProjectId(null); }}
        >
          🎙 TTS Studio
        </span>
        {page === "project" && projectId && (
          <>
            <span style={{ color: "#475569" }}>/</span>
            <span style={{ color: "#94a3b8" }}>项目详情</span>
          </>
        )}
        {page === "settings" && (
          <>
            <span style={{ color: "#475569" }}>/</span>
            <span style={{ color: "#94a3b8" }}>系统配置</span>
          </>
        )}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => setPage(page === "settings" ? "home" : "settings")}
          style={{
            background: "transparent",
            color: page === "settings" ? "#3b82f6" : "#94a3b8",
            border: "1px solid " + (page === "settings" ? "#3b82f6" : "#334155"),
            borderRadius: 6,
            padding: "4px 14px",
            cursor: "pointer",
            fontSize: 13,
            fontWeight: 600,
          }}
        >
          ⚙️ 设置
        </button>
      </header>

      <main style={{ padding: 24 }}>
        {page === "settings" ? (
          <SettingsPage />
        ) : page === "project" && projectId ? (
          <ProjectDetail projectId={projectId} onBack={() => { setPage("home"); setProjectId(null); }} />
        ) : (
          <ProjectList onSelect={(id) => { setProjectId(id); setPage("project"); }} />
        )}
      </main>
    </div>
  );
}