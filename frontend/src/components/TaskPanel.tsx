import React, { useState, useEffect, useRef } from "react";
import { api } from "../api";

interface Props {
  projectId: string;
}

const TaskPanel: React.FC<Props> = ({ projectId }) => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [expandedTask, setExpandedTask] = useState<string | null>(null);
  const [cancellingMap, setCancellingMap] = useState<Record<string, boolean>>({});
  const pollingRef = useRef<number | null>(null);

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const r = await api.listLLMTasks(projectId);
      // r.tasks might be an array or a single dict; normalize
      let list: any[] = [];
      if (Array.isArray(r.tasks)) {
        list = r.tasks;
      } else if (r.tasks && typeof r.tasks === "object") {
        list = [r.tasks];
      }
      // Sort by created_at descending
      list.sort((a: any, b: any) => {
        const ta = a.created_at || a.updated_at || "";
        const tb = b.created_at || b.updated_at || "";
        return tb.localeCompare(ta);
      });
      setTasks(list);
    } catch (e: any) {
      console.error("Failed to fetch tasks:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
    // Auto-poll every 3s if any task is running
    pollingRef.current = window.setInterval(() => {
      // Check if any task is still active
      const hasRunning = tasks.some(t => 
        t.status === "running" || t.status === "running:generating" || t.status === "pending"
      );
      if (hasRunning) {
        fetchTasks();
      }
    }, 3000);
    return () => {
      if (pollingRef.current !== null) {
        clearInterval(pollingRef.current);
      }
    };
  }, [projectId]);

  const handleCancelTask = async (taskId: string) => {
    if (cancellingMap[taskId]) return;
    setCancellingMap(prev => ({ ...prev, [taskId]: true }));
    try {
      await api.cancelLLMTask(projectId, taskId);
      await fetchTasks();
    } catch (e: any) {
      const msg = e.message || "";
      if (msg.includes("404:")) {
        await fetchTasks();
        return;
      }
      if (msg.includes("409:")) {
        try {
          const body = msg.slice(4);
          const parsed = JSON.parse(body);
          alert(parsed.detail || body);
        } catch {
          alert(msg.slice(4));
        }
        await fetchTasks();
        return;
      }
      alert(msg || "取消失败");
    } finally {
      setCancellingMap(prev => ({ ...prev, [taskId]: false }));
    }
  };

  const getStatusStyle = (status: string) => {
    switch (status) {
      case "complete": return { bg: "#065f46", color: "#6ee7b7" };
      case "running":
      case "running:generating":
      case "pending": return { bg: "#1e3a5f", color: "#93c5fd" };
      case "error":
      case "timeout": return { bg: "#7f1d1d", color: "#fca5a5" };
      case "cancelled": return { bg: "#374151", color: "#9ca3af" };
      default: return { bg: "#374151", color: "#d1d5db" };
    }
  };

  const statusLabel = (s: string) => {
    const labels: Record<string, string> = {
      "complete": "✅ 完成",
      "running": "⏳ 运行中",
      "running:generating": "⏳ LLM 生成中",
      "pending": "⏳ 等待中",
      "error": "❌ 失败",
      "timeout": "⏰ 超时",
      "cancelled": "🚫 已取消",
    };
    return labels[s] || s;
  };

  const typeLabel = (t: string) => {
    const labels: Record<string, string> = {
      "outline": "生成大纲",
      "dialogues": "生成对白",
      "dialogue_generation": "生成对白",
      "continuation": "续写剧集",
      "generate_batch": "批量生成音频",
      "refresh": "刷新状态",
      "single_audio": "单条音频生成", // #103: add single_audio label
      "apply_effects": "应用音效", // #103: add apply_effects label
    };
    return labels[t] || t;
  };

  const containerStyle: React.CSSProperties = {
    background: "#0f1117", borderRadius: 8, padding: 16,
    border: "1px solid #1e293b",
  };

  const headerStyle: React.CSSProperties = {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    marginBottom: 12,
  };

  const titleStyle: React.CSSProperties = {
    fontSize: 15, fontWeight: 600, color: "#e2e8f0",
  };

  const cardStyle: React.CSSProperties = {
    background: "#1e293b", borderRadius: 6, padding: 12, marginBottom: 8,
    border: "1px solid #334155",
  };

  const rowStyle: React.CSSProperties = {
    display: "flex", gap: 8, alignItems: "center", fontSize: 13,
    color: "#cbd5e1",
  };

  const progressBarStyle: React.CSSProperties = {
    background: "#334155", borderRadius: 4, height: 6, flex: 1, overflow: "hidden",
  };

  const progressFillStyle = (pct: number): React.CSSProperties => ({
    background: pct === 100 ? "#22c55e" : "#3b82f6",
    width: `${pct}%`, height: "100%", borderRadius: 4,
    transition: "width 0.5s ease",
  });

  const cancelBtnStyle: React.CSSProperties = {
    background: "transparent",
    border: "1px solid #ef4444",
    color: "#ef4444",
    borderRadius: 4,
    padding: "2px 8px",
    cursor: "pointer",
    fontSize: 11,
    fontWeight: 500,
  };

  const btnStyle: React.CSSProperties = {
    background: "transparent", border: "1px solid #334155",
    color: "#94a3b8", borderRadius: 6, padding: "4px 12px",
    cursor: "pointer", fontSize: 12,
  };

  const hasRunning = tasks.some(t =>
    t.status === "running" || t.status === "running:generating" || t.status === "pending"
  );

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>
          📋 LLM 生成任务
          {hasRunning && <span style={{ fontSize: 11, color: "#93c5fd", marginLeft: 8 }}>● 活跃</span>}
        </div>
        <button onClick={fetchTasks} disabled={loading} style={btnStyle}>
          {loading ? "⏳ 刷新中..." : "🔄 刷新"}
        </button>
      </div>
      {tasks.length === 0 && !loading && (
        <div style={{ textAlign: "center", padding: 24, color: "#64748b", fontSize: 13 }}>
          暂无 LLM 生成任务记录
        </div>
      )}
      {tasks.map((task: any, i: number) => {
        const statusStyle = getStatusStyle(task.status || "");
        const isExpanded = expandedTask === `${i}`;
        const pct = task.total && task.total > 0
          ? Math.round((task.current || 0) / task.total * 100)
          : (task.status === "complete" ? 100 : 0);
        const st = statusLabel(task.status || "");
        const tt = typeLabel(task.type || task.task_type || "");

        return (
          <div key={i} style={cardStyle}>
            <div style={rowStyle}>
              <span style={{ background: statusStyle.bg, color: statusStyle.color,
                padding: "2px 6px", borderRadius: 4, fontSize: 11, fontWeight: 600 }}>
                {st}
              </span>
              <span style={{ fontWeight: 500 }}>
                {task.type === "apply_effects" && task.extra?.char_name /* #108 */
                  ? <>为「{task.extra.char_name}」{tt}</>
                  : tt}
              </span>
              <span style={{ color: "#64748b", fontSize: 11 }}>
                {task.created_at?.slice(5, 16) || task.updated_at?.slice(5, 16) || ""}
              </span>
              <div style={{ flex: 1 }} />
              {(task.status === "running" || task.status === "running:generating" || task.status === "pending") && (
                <button
                  onClick={() => handleCancelTask(task.id || task.task_id)}
                  disabled={cancellingMap[task.id || task.task_id]}
                  style={{
                    ...cancelBtnStyle,
                    color: cancellingMap[task.id || task.task_id] ? "#9ca3af" : "#ef4444",
                    cursor: cancellingMap[task.id || task.task_id] ? "not-allowed" : "pointer",
                  }}
                >
                  {cancellingMap[task.id || task.task_id] ? "⏳ 终止中..." : "✕ 终止"}
                </button>
              )}
              {task.total && task.total > 0 && (
                <span style={{ color: "#94a3b8", fontSize: 11 }}>
                  {task.current || 0}/{task.total}
                </span>
              )}
              <button onClick={() => setExpandedTask(isExpanded ? null : `${i}`)}
                style={{ background: "none", border: "none", color: "#64748b", cursor: "pointer", fontSize: 16 }}>
                {isExpanded ? "▲" : "▼"}
              </button>
            </div>
            {task.total && task.total > 0 && (
              <div style={{ ...progressBarStyle, margin: "6px 0" }}>
                <div style={progressFillStyle(pct)} />
              </div>
            )}
            {isExpanded && (
              <div style={{ marginTop: 8, background: "#0f1117", borderRadius: 4, padding: 8, fontSize: 12, color: "#94a3b8", overflowX: "auto" }}>
                <pre style={{ margin: 0, whiteSpace: "pre-wrap", wordBreak: "break-all" }}>
                  {JSON.stringify(task, null, 2)}
                </pre>
              </div>
            )}
            {task.error && (
              <div style={{ marginTop: 6, color: "#fca5a5", fontSize: 12 }}>
                ⚠️ {task.error}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default TaskPanel;