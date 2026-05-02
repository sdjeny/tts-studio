import { useState } from "react";
import ProjectList from "./pages/ProjectList";
import ProjectDetail from "./pages/ProjectDetail";

export default function App() {
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
          onClick={() => setProjectId(null)}
        >
          🎙 TTS Studio
        </span>
        {projectId && (
          <>
            <span style={{ color: "#475569" }}>/</span>
            <span style={{ color: "#94a3b8" }}>项目详情</span>
          </>
        )}
      </header>

      <main style={{ padding: 24 }}>
        {projectId ? (
          <ProjectDetail projectId={projectId} onBack={() => setProjectId(null)} />
        ) : (
          <ProjectList onSelect={setProjectId} />
        )}
      </main>
    </div>
  );
}