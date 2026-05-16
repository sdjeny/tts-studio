import { useState, useRef } from "react";
import { api, Project } from "../api";
import DialogueList from "./DialogueList";
import Timeline from "./Timeline";

/** 从项目所有对白中提取去重后的角色名（不含旁白/场景） */
function extractAllCharNames(project: Project): string[] {
  const names = new Set<string>();
  for (const ep of project.episodes) {
    for (const dlg of ep.dialogues || []) {
      const n = (dlg.character_name || "").trim();
      if (n && n !== "旁白" && n !== "场景") names.add(n);
    }
  }
  return Array.from(names).sort();
}

export default function EpisodePanel({ project, onChange, onError }: {
  project: Project; onChange: () => void; onError: (m: string) => void;
}) {
  const [title, setTitle] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);
  const [batchMode, setBatchMode] = useState<"pending" | "all">("pending");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [batchRefreshProgress, setBatchRefreshProgress] = useState<Record<string, { current: number; total: number; errors: string[] }>>({});
  const importFileInputRef = useRef<HTMLInputElement>(null);

  // 批量换角 state
  const [showBatchReplace, setShowBatchReplace] = useState(false);
  const [batchOldName, setBatchOldName] = useState("");
  const [batchNewName, setBatchNewName] = useState("");
  const [batchEpIds, setBatchEpIds] = useState<Set<string>>(new Set());

  const add = async () => {
    if (!title.trim()) return;
    try {
      await api.createEpisode(project.id, title.trim());
      setTitle("");
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const remove = async (eid: string) => {
    if (!confirm("删除该剧集及其所有对白？")) return;
    try { await api.deleteEpisode(project.id, eid); onChange(); }
    catch (e: any) { onError(e.message); }
  };

  const dlAll = (eid: string) => {
    window.open(api.downloadEpisodeAll(project.id, eid), "_blank");
  };

  const [showDownloadMenu, setShowDownloadMenu] = useState<Record<string, boolean>>({});

  const hasAnyAudio = (ep: any) => {
    return ep.dialogues?.some((d: any) => d.current_audio_id);
  };

  const handleConcatenateDownload = async (ep: any) => {
    if (!hasAnyAudio(ep)) {
      onError("⚠️ 该剧集没有任何音频，无法混音");
      return;
    }
    try {
      const blob = await api.concatenateEpisodeAudio(project.id, ep.id, { gap: 0.5, format: "wav", sample_rate: 24000 });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${ep.title || "episode"}_concat.wav`;
      a.click();
      URL.revokeObjectURL(url);
      onError("✅ 混音导出完成");
    } catch (e: any) { onError(e.message); }
  };

  const batchGenerate = async (ep: Project["episodes"][0]) => {
    const targets = batchMode === "all"
      ? ep.dialogues
      : ep.dialogues.filter((d: any) => !d.current_audio_id);

    if (targets.length === 0) {
      onError(batchMode === "all" ? "✅ 没有可生成的对白" : "✅ 所有对白已有音频，无需生成");
      return;
    }

    const label = batchMode === "all" ? "全部重新生成" : "仅生成未生成过的";
    if (!confirm(`[${label}] 对 ${targets.length} 条对白生成音频？`)) return;

    const dlgIds = targets.map((d: any) => d.id);
    try {
      const result = await api.generateBatchAudio(project.id, ep.id, dlgIds);
      onError(`⏳ 已提交 ${result.total} 条 TTS 任务，后台生成中...`);
      // 轮询进度
      const pollInterval = setInterval(async () => {
        try {
          const resp = await fetch(`/api/projects/${project.id}/generation-status`);
          if (!resp.ok) {
            clearInterval(pollInterval);
            onError("轮询请求失败: " + resp.statusText);
            return;
          }
          const status = await resp.json();
          if (status.status === "complete") {
            clearInterval(pollInterval);
            onChange();
            onError(`✅ 全部完成！共 ${status.total || result.total} 条`);
          } else if (status.status === "error") {
            clearInterval(pollInterval);
            onError(`❌ 生成失败: ${status.error}`);
          } else if (status.current !== undefined && status.total) {
            onError(`⏳ 进度 ${status.current}/${status.total}...`);
          }
        } catch (e: any) {
          clearInterval(pollInterval);
          onError(`轮询失败: ${e.message}`);
        }
      }, 2000);
      // 60秒超时
      setTimeout(() => clearInterval(pollInterval), 60000);
    } catch (e: any) {
      onError(`批量生成请求失败: ${e.message}`);
    }
  };

  const exportEpisode = async (ep: Project["episodes"][0]) => {
    try {
      const data = await api.exportEpisode(project.id, ep.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${ep.title}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e: any) { onError(e.message); }
  };

  const importDialogues = async (epId: string) => {
    const input = importFileInputRef.current;
    if (!input) return;
    input.onchange = async (e: any) => {
      const file = e.target.files?.[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        const dialogues = data.dialogues || data;
        const items = Array.isArray(dialogues) ? dialogues : [dialogues];
        await api.importDialogues(project.id, epId, {
          title: data.title || "",
          dialogues: items.map((d: any) => ({
            character_id: d.character_id || "",
            text: d.text || "",
            instruct: d.instruct || "",
            order: d.order || 0,
          })),
        });
        onChange();
        onError(`✅ 成功导入 ${items.length} 条对白`);
      } catch (err: any) {
        onError(`导入失败: ${err.message}`);
      }
      input.value = "";
    };
    input.click();
  };

  return (
    <div>
      <input ref={importFileInputRef} type="file" accept=".json" style={{ display: "none" }} />

      {/* 添加剧集 */}
      <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
        <input
          placeholder="剧集标题（如：第一集）" value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && add()}
          style={{ flex: 1, padding: "9px 14px", background: "#1e293b", border: "1px solid #334155", borderRadius: 8, color: "#e2e8f0", fontSize: 14, outline: "none" }}
        />
        <button onClick={add} style={{ padding: "9px 20px", background: "#3b82f6", color: "#fff", border: "none", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}>
          + 新建剧集
        </button>
      </div>

      {/* 批量换角工具栏 */}
      {project.episodes.length > 0 && (
        <div style={{ marginBottom: 12 }}>
          <button
            onClick={() => setShowBatchReplace(!showBatchReplace)}
            style={{ ...smallBtn, color: batchOldName ? "#f59e0b" : "#94a3b8", borderColor: batchOldName ? "#78350f" : "#334155" }}
          >
            🔄 批量换角 {showBatchReplace ? "▾" : "▸"}
          </button>
          {showBatchReplace && (
            <div style={{
              marginTop: 8, padding: 14, background: "#1c1917", border: "1px solid #78350f",
              borderRadius: 8, display: "grid", gap: 10,
            }}>
              <div style={{ fontSize: 13, color: "#fbbf24", fontWeight: 600 }}>
                🔄 批量换角 — 将选中章节里的某个角色替换为另一个角色
              </div>
              {/* 角色选择 */}
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 12, color: "#94a3b8" }}>将</span>
                {batchOldName ? (
                  <select value={batchOldName} onChange={e => setBatchOldName(e.target.value)} style={{ ...inputSm, minWidth: 100 }}>
                    <option value="">选择角色…</option>
                    {extractAllCharNames(project).map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                ) : (
                  <select value="" onChange={e => setBatchOldName(e.target.value)} style={{ ...inputSm, minWidth: 100 }}>
                    <option value="">选择角色…</option>
                    {extractAllCharNames(project).map(n => <option key={n} value={n}>{n}</option>)}
                  </select>
                )}
                <span style={{ fontSize: 12, color: "#94a3b8" }}>替换为</span>
                <input
                  value={batchNewName}
                  onChange={e => setBatchNewName(e.target.value)}
                  placeholder="新角色名（如：小明青年）"
                  style={{ ...inputSm, minWidth: 140 }}
                />
                <span style={{ fontSize: 12, color: "#94a3b8" }}>·</span>
                <button
                  onClick={() => {
                    if (!batchOldName.trim()) { onError("请先选择要替换的角色"); return; }
                    if (!batchNewName.trim()) { onError("请输入新角色名"); return; }
                    const epIds = batchEpIds.size > 0 ? Array.from(batchEpIds) : [];
                    const scope = epIds.length > 0 ? `选中 ${epIds.length} 个章节` : "所有章节";
                    if (!confirm(`确定将「${batchOldName}」替换为「${batchNewName}」？\n作用范围：${scope}\n\n此操作不可撤销。`)) return;
                    setLoading(true);
                    (async () => {
                      try {
                        const r = await api.batchReplaceCharacter(project.id, batchOldName.trim(), batchNewName.trim(), epIds);
                        onChange();
                        onError(`✅ 已替换 ${r.replaced} 条对白（涉及 ${r.affected_episodes} 个章节）`);
                        setBatchOldName("");
                        setBatchNewName("");
                        setBatchEpIds(new Set());
                        setShowBatchReplace(false);
                      } catch (e: any) { onError(e.message); }
                      finally { setLoading(false); }
                    })();
                  }}
                  disabled={loading}
                  style={{
                    padding: "5px 14px", background: loading ? "#78350f" : "#f59e0b",
                    color: loading ? "#a8a29e" : "#1c1917", border: "none", borderRadius: 4,
                    cursor: loading ? "wait" : "pointer", fontWeight: 700, fontSize: 12,
                  }}
                >
                  {loading ? "执行中…" : "⚠️ 确认替换"}
                </button>
              </div>
              {/* 章节范围选择 */}
              <div>
                <div style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
                  作用章节范围（不选 = 所有章节）：
                </div>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {project.episodes.map((ep, i) => {
                    const selected = batchEpIds.has(ep.id);
                    return (
                      <button
                        key={ep.id}
                        onClick={() => {
                          setBatchEpIds(prev => {
                            const next = new Set(prev);
                            selected ? next.delete(ep.id) : next.add(ep.id);
                            return next;
                          });
                        }}
                        style={{
                          padding: "2px 8px", borderRadius: 4, fontSize: 11,
                          border: `1px solid ${selected ? "#f59e0b" : "#334155"}`,
                          background: selected ? "#f59e0b22" : "transparent",
                          color: selected ? "#f59e0b" : "#64748b",
                          cursor: "pointer",
                        }}
                      >
                        {i + 1}. {ep.title.length > 8 ? ep.title.slice(0, 8) + "…" : ep.title}
                      </button>
                    );
                  })}
                  {batchEpIds.size > 0 && (
                    <button
                      onClick={() => setBatchEpIds(new Set())}
                      style={{ padding: "2px 8px", borderRadius: 4, fontSize: 11, background: "transparent", border: "1px solid #334155", color: "#64748b", cursor: "pointer" }}
                    >清除选择</button>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 剧集列表 */}
      {project.episodes.length === 0 ? (
        <p style={{ color: "#64748b", textAlign: "center", padding: 40 }}>暂无剧集</p>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {project.episodes.map((ep) => (
            <div key={ep.id} style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 10, overflow: "hidden" }}>
              {/* 剧集头部 */}
              <div
                onClick={() => setExpanded(expanded === ep.id ? null : ep.id)}
                style={{ padding: "14px 18px", cursor: "pointer", display: "flex", justifyContent: "space-between", alignItems: "center" }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontWeight: 600 }}>📺 {ep.title}</span>
                  <span style={{ color: "#64748b", fontSize: 13 }}>
                    {ep.dialogues.length} 条对白
                  </span>
                  {/* 剧集风格开关 */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      const newVal = !ep.style_enabled;
                      // 乐观更新 UI
                      ep.style_enabled = newVal;
                      api.updateEpisode(project.id, ep.id, { style_enabled: newVal })
                        .then(() => onChange())
                        .catch((err: any) => { onError(err.message); onChange(); });
                    }}
                    style={{
                      fontSize: 10,
                      padding: "1px 6px",
                      borderRadius: 4,
                      border: "1px solid",
                      borderColor: ep.style_enabled ? "#f59e0b" : "#334155",
                      background: ep.style_enabled ? "#f59e0b22" : "transparent",
                      color: ep.style_enabled ? "#f59e0b" : "#64748b",
                      cursor: "pointer",
                    }}
                  >
                    🎭 风格{ep.style_enabled ? "开" : "关"}
                  </button>
                </div>
                <div style={{ display: "flex", gap: 6 }}>
                  <span style={{ color: "#64748b", fontSize: 18 }}>{expanded === ep.id ? "▾" : "▸"}</span>
                </div>
              </div>

              {/* 展开内容 */}
              {expanded === ep.id && (
                <div style={{ borderTop: "1px solid #334155", padding: 16 }}>
                  {/* 摘要区 */}
                  <div style={{ marginBottom: 12 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                      <label style={{ fontSize: 12, color: "#94a3b8" }}>📋 剧集摘要</label>
                      <button onClick={async () => {
                        try {
                          await api.updateEpisode(project.id, ep.id, { summary: ep.summary });
                          onError("✅ 摘要已保存");
                        } catch (e: any) { onError(e.message); }
                      }} style={{ ...smallBtn, fontSize: 11, padding: "1px 8px" }}>保存</button>
                    </div>
                    <textarea
                      value={ep.summary || ""}
                      onChange={(e) => {
                        ep.summary = e.target.value;
                      }}
                      placeholder="输入剧集摘要，AI 生成对白的上下文..."
                      rows={2}
                      style={{ ...inputSm, width: "100%", resize: "vertical", minHeight: 40 }}
                    />
                  </div>

                  <div style={{ display: "flex", gap: 6, marginBottom: 12, alignItems: "center", flexWrap: "wrap" }}>
                    <div style={{ display: "flex", gap: 0, alignItems: "center" }}>
                      <button onClick={() => batchGenerate(ep)} style={{ ...smallBtn, color: "#22c55e", borderColor: "#22c55e", borderRadius: "4px 0 0 4px" }}>
                        🔊 生成全部音频
                      </button>
                      <select
                        value={batchMode}
                        onChange={(e) => setBatchMode(e.target.value as "pending" | "all")}
                        style={{ ...smallBtn, borderRadius: "0 4px 4px 0", borderLeft: "none", color: "#94a3b8", padding: "3px 4px" }}
                      >
                        <option value="pending">仅未生成</option>
                        <option value="all">全部重新生成</option>
                      </select>
                    </div>

                    <button onClick={() => dlAll(ep.id)} style={smallBtn}>⬇ 下载全部音频</button>
                    {/* Download dropdown */}
                    <div style={{ position: "relative", display: "inline-flex" }}>
                      <button
                        onClick={() => setShowDownloadMenu(prev => ({ ...prev, [ep.id]: !prev[ep.id] }))}
                        style={{ ...smallBtn, borderRadius: "0 4px 4px 0", borderLeft: "none", padding: "3px 6px" }}
                      >▾</button>
                      {showDownloadMenu[ep.id] && (
                        <div style={{
                          position: "absolute", top: "100%", right: 0, marginTop: 2,
                          background: "#1e293b", border: "1px solid #334155", borderRadius: 6,
                          boxShadow: "0 4px 12px rgba(0,0,0,0.4)", zIndex: 20, minWidth: 180,
                        }}>
                          <button
                            onClick={() => { dlAll(ep.id); setShowDownloadMenu(prev => ({ ...prev, [ep.id]: false })); }}
                            style={{ display: "block", width: "100%", textAlign: "left", padding: "6px 12px", background: "none", border: "none", color: "#e2e8f0", fontSize: 12, cursor: "pointer" }}
                          >📦 打包下载 (ZIP)</button>
                          <button
                            onClick={() => { handleConcatenateDownload(ep); setShowDownloadMenu(prev => ({ ...prev, [ep.id]: false })); }}
                            style={{ display: "block", width: "100%", textAlign: "left", padding: "6px 12px", background: "none", border: "none", color: "#e2e8f0", fontSize: 12, cursor: "pointer", borderTop: "1px solid #334155" }}
                          >🎵 混音为单个文件</button>
                        </div>
                      )}
                    </div>
                    {(() => {
                      const curEp = project.episodes.find((e: any) => e.id === expanded) || ep;
                      const hasGenerating = curEp.dialogues?.some((d: any) =>
                        d.audio_history?.some((a: any) => a.status === "generating")
                      );
                      const isRefreshing = refreshing === curEp.id;
                      const refreshProgress = batchRefreshProgress[curEp.id];
                      return (
                        <>
                          <button
                            onClick={async () => {
                              if (!hasGenerating) return;
                              setRefreshing(curEp.id);
                              setBatchRefreshProgress(prev => ({ ...prev, [curEp.id]: { current: 0, total: curEp.dialogues.length, errors: [] } }));
                              onError("");

                              const dlgIds = curEp.dialogues.map((d: any) => d.id);
                              try {
                                const resp = await api.generateBatchRefresh(project.id, curEp.id, dlgIds);
                                if (!resp.ok) {
                                  onError("批量刷新请求失败: " + resp.statusText);
                                  setRefreshing(null);
                                  setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                  return;
                                }
                                const result = await resp.json();
                                setBatchRefreshProgress(prev => ({ ...prev, [curEp.id]: { current: 0, total: result.total, errors: [] } }));
                                // 轮询进度
                                const pollInterval = setInterval(async () => {
                                  try {
                                    const statusResp = await fetch(`/api/projects/${project.id}/generation-status`);
                                    if (!statusResp.ok) {
                                      clearInterval(pollInterval);
                                      onError("轮询请求失败: " + statusResp.statusText);
                                      setRefreshing(null);
                                      setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                      return;
                                    }
                                    const status = await statusResp.json();
                                    if (status.status === "complete") {
                                      clearInterval(pollInterval);
                                      setRefreshing(null);
                                      setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                      onChange();
                                      onError(`✅ 全部刷新成功！共 ${status.total || result.total} 条`);
                                    } else if (status.status === "error") {
                                      clearInterval(pollInterval);
                                      setRefreshing(null);
                                      setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                      onError(`❌ 刷新失败: ${status.error}`);
                                    } else if (status.current !== undefined && status.total) {
                                      setBatchRefreshProgress(prev => ({ ...prev, [curEp.id]: { current: status.current!, total: status.total!, errors: [] } }));
                                    }
                                  } catch (e: any) {
                                    clearInterval(pollInterval);
                                    setRefreshing(null);
                                    setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                    onError(`轮询失败: ${e.message}`);
                                  }
                                }, 2000);
                                setTimeout(() => clearInterval(pollInterval), 60000);
                              } catch (e: any) {
                                setRefreshing(null);
                                setBatchRefreshProgress(prev => { const n = { ...prev }; delete n[curEp.id]; return n; });
                                onError(`批量刷新请求失败: ${e.message}`);
                              }
                            }}
                            disabled={!hasGenerating || isRefreshing}
                            title={hasGenerating ? "刷新所有对白的生成状态" : "当前没有进行中的生成任务"}
                            style={{
                              ...smallBtn,
                              color: hasGenerating || isRefreshing ? "#3b82f6" : "#64748b",
                              borderColor: hasGenerating || isRefreshing ? "#3b82f6" : "#334155",
                              cursor: hasGenerating || isRefreshing ? "pointer" : "not-allowed",
                              opacity: isRefreshing ? 0.7 : 1,
                            }}
                          >
                            {isRefreshing ? `⏳ 刷新中 ${refreshProgress ? `${refreshProgress.current}/${refreshProgress.total}` : "..."}` : hasGenerating ? "🔄 刷新状态" : "🔄 无进行中"}
                          </button>
                        </>
                      );
                    })()}

                    {/* 导入导出 */}
                    <button onClick={() => exportEpisode(ep)} style={{ ...smallBtn, color: "#f59e0b", borderColor: "#f59e0b" }}>📤 导出</button>
                    <button onClick={() => importDialogues(ep.id)} style={{ ...smallBtn, color: "#f59e0b", borderColor: "#f59e0b" }}>📥 导入</button>

                    <div style={{ flex: 1 }} />

                    {(ep.dialogues?.length ?? 0) > 0 && (
                      <button onClick={async () => {
                        const count = ep.dialogues.length;
                        if (!confirm(`⚠️ 不可逆操作！\n\n将删除该剧集全部 ${count} 条对白及其所有音频文件（磁盘文件一并删除）。\n\n确定要继续吗？`)) return;
                        try {
                          const r = await api.purgeEpisodeDialogues(project.id, ep.id);
                          onChange();
                          onError(`✅ 已清空 ${r.deleted_dialogues} 条对白，删除 ${r.deleted_files} 个音频文件`);
                        } catch (e: any) { onError(e.message); }
                      }} style={{ ...smallBtn, color: "#f59e0b", borderColor: "#f59e0b" }}>🗑 清空对白</button>
                    )}
                    <button onClick={() => remove(ep.id)} style={{ ...smallBtn, color: "#ef4444", borderColor: "#ef4444" }}>🗑 删除</button>
                  </div>
                  {/* Timeline editor */}
                  <Timeline
                    project={project}
                    episode={ep}
                    onChange={onChange}
                    onError={onError}
                  />

                  <DialogueList
                    project={project}
                    episode={ep}
                    onChange={onChange}
                    onError={onError}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const smallBtn: React.CSSProperties = {
  background: "transparent", color: "#94a3b8",
  border: "1px solid #334155", borderRadius: 4,
  padding: "3px 10px", cursor: "pointer", fontSize: 12,
};
const inputSm: React.CSSProperties = {
  padding: "5px 8px", background: "#1e293b", border: "1px solid #334155",
  borderRadius: 4, color: "#e2e8f0", fontSize: 13, outline: "none",
};
