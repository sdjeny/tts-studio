import { useEffect, useState, useCallback } from "react";
import { api, Project } from "../api";

export default function ProjectList({ onSelect }: { onSelect: (id: string) => void }) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState("");

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setProjects(await api.listProjects());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!name.trim()) return;
    try {
      await api.createProject(name.trim());
      setName("");
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("确定删除该项目？")) return;
    try {
      await api.deleteProject(id);
      await load();
    } catch (e: any) {
      setError(e.message);
    }
  };

  if (loading) return <p style={{ color: "#64748b" }}>加载中...</p>;

  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <h2 style={{ marginBottom: 20, fontSize: 22 }}>📁 项目工程</h2>

      {error && (
        <div style={{ background: "#7f1d1d", color: "#fca5a5", padding: "8px 12px", borderRadius: 6, marginBottom: 12 }}>
          {error}
        </div>
      )}

      {/* 新建项目 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && create()}
          placeholder="输入项目名称..."
          style={{
            flex: 1,
            padding: "10px 14px",
            background: "#1e293b",
            border: "1px solid #334155",
            borderRadius: 8,
            color: "#e2e8f0",
            fontSize: 14,
            outline: "none",
          }}
        />
        <button
          onClick={create}
          style={{
            padding: "10px 20px",
            background: "#3b82f6",
            color: "#fff",
            border: "none",
            borderRadius: 8,
            cursor: "pointer",
            fontWeight: 600,
          }}
        >
          + 新建项目
        </button>
      </div>

      {/* 项目列表 */}
      {projects.length === 0 ? (
        <p style={{ color: "#64748b", textAlign: "center", padding: 40 }}>暂无项目，创建一个开始吧</p>
      ) : (
        <div style={{ display: "grid", gap: 12 }}>
          {projects.map((p) => (
            <div
              key={p.id}
              style={{
                background: "#1e293b",
                border: "1px solid #334155",
                borderRadius: 10,
                padding: "16px 20px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                cursor: "pointer",
              }}
              onClick={() => onSelect(p.id)}
            >
              <div onClick={() => onSelect(p.id)} style={{ flex: 1, cursor: "pointer" }}>
                {renamingId === p.id ? (
                  <form onSubmit={async (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                    if (!renameDraft.trim()) return;
                    try {
                      await api.updateProject(p.id, renameDraft.trim());
                      setRenamingId(null);
                      await load();
                    } catch (e: any) { setError(e.message); }
                  }} style={{ display: "flex", gap: 6, alignItems: "center" }}>
                    <input
                      value={renameDraft}
                      onChange={(e) => setRenameDraft(e.target.value)}
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                      style={{ fontSize: 15, fontWeight: 600, background: "#1e293b", border: "1px solid #3b82f6", borderRadius: 6, padding: "3px 8px", color: "#e2e8f0", outline: "none" }}
                    />
                    <button type="submit" onClick={(e) => e.stopPropagation()} style={{ background: "transparent", color: "#3b82f6", border: "1px solid #3b82f6", borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 12 }}>保存</button>
                    <button type="button" onClick={(e) => { e.stopPropagation(); setRenamingId(null); }} style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 12 }}>取消</button>
                  </form>
                ) : (
                  <div style={{ fontWeight: 600, fontSize: 16 }}>{p.name}</div>
                )}
                <div style={{ color: "#64748b", fontSize: 12, marginTop: 4, display: "flex", gap: 12, flexWrap: "wrap" }}>
                  <span>{p.characters.length} 角色 · {p.episodes.length} 剧集</span>
                  <span style={{ color: "#475569" }}>创建: {p.created_at?.slice(0, 16) || "时间未知"}</span>
                  <span style={{ color: "#475569" }}>修改: {(p.updated_at || p.created_at)?.slice(0, 16) || "时间未知"}</span>
                </div>
              </div>
              <div style={{ display: "flex", gap: 6 }}>
                <button
                  onClick={(e) => { e.stopPropagation(); setRenameDraft(p.name); setRenamingId(p.id); }}
                  style={{ background: "transparent", color: "#94a3b8", border: "1px solid #334155", borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                >重命名</button>
                <button
                  onClick={(e) => { e.stopPropagation(); remove(p.id); }}
                  style={{ background: "transparent", color: "#ef4444", border: "1px solid #ef4444", borderRadius: 6, padding: "4px 10px", cursor: "pointer", fontSize: 12 }}
                >删除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}