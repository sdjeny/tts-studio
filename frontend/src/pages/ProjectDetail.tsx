import { useEffect, useState, useCallback, useRef } from "react";
import { api, Project } from "../api";
import CharacterPanel from "../components/CharacterPanel";
import EpisodePanel from "../components/EpisodePanel";
import ProjectSettings from "../components/ProjectSettings";

type Tab = "ai" | "episodes" | "characters" | "settings";

export default function ProjectDetail({ projectId, onBack }: { projectId: string; onBack: () => void }) {
  const [project, setProject] = useState<Project | null>(null);
  const [tab, setTab] = useState<Tab>("ai");
  const [error, setError] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [nameDraft, setNameDraft] = useState("");
  const projectImportRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setProject(await api.getProject(projectId));
    } catch (e: any) {
      setError(e.message);
    }
  }, [projectId]);

  useEffect(() => { load(); }, [load]);

  if (!project) return <p style={{ color: "#64748b" }}>加载中...</p>;

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <input ref={projectImportRef} type="file" accept=".json" style={{ display: "none" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
        <button onClick={onBack} style={btnGhost}>← 返回</button>
        {editingName ? (
          <form onSubmit={async (e) => {
            e.preventDefault();
            if (!nameDraft.trim()) return;
            try {
              await api.updateProject(projectId, nameDraft.trim());
              setNameDraft("");
              setEditingName(false);
              await load();
            } catch (e: any) { setError(e.message); }
          }} style={{ display: "flex", gap: 6, alignItems: "center" }}>
            <input
              value={nameDraft}
              onChange={(e) => setNameDraft(e.target.value)}
              autoFocus
              style={{ fontSize: 18, fontWeight: 700, background: "#1e293b", border: "1px solid #3b82f6", borderRadius: 6, padding: "4px 10px", color: "#e2e8f0", outline: "none" }}
            />
            <button type="submit" style={{ ...btnGhost, color: "#3b82f6", borderColor: "#3b82f6", fontSize: 12 }}>保存</button>
            <button type="button" onClick={() => setEditingName(false)} style={{ ...btnGhost, fontSize: 12 }}>取消</button>
          </form>
        ) : (
          <h2 style={{ fontSize: 22, margin: 0, cursor: "pointer" }} onClick={() => { setNameDraft(project.name); setEditingName(true); }} title="点击修改项目名称">
            {project.name} <span style={{ fontSize: 14, color: "#64748b", fontWeight: 400 }}>✏️</span>
          </h2>
        )}
        <div style={{ flex: 1 }} />
        <button onClick={async () => {
          try {
            const data = await api.exportProject(projectId);
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `${project.name}.json`;
            a.click();
            URL.revokeObjectURL(url);
          } catch (e: any) { setError(e.message); }
        }} style={{ ...btnGhost, color: "#a855f7", borderColor: "#a855f7" }}>📤 导出项目</button>
        <button onClick={() => {
          if (!projectImportRef.current) return;
          projectImportRef.current.onchange = async (e: any) => {
            const file = e.target.files?.[0];
            if (!file) return;
            try {
              const text = await file.text();
              const data = JSON.parse(text);
              await api.importProject(projectId, data);
              await load();
              setError(`✅ 项目导入成功`);
            } catch (err: any) {
              setError(`导入失败: ${err.message}`);
            }
            e.target.value = "";
          };
          projectImportRef.current.click();
        }} style={{ ...btnGhost, color: "#a855f7", borderColor: "#a855f7" }}>📥 导入项目</button>
      </div>

      {error && <div style={error.startsWith("✅") ? successBox : errorBox}>{error}</div>}

      {/* tabs */}
      <div style={{ display: "flex", gap: 4, marginBottom: 20 }}>
        {(["ai", "characters", "episodes", "settings"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} style={tab === t ? btnTabActive : btnTab}>
            {t === "ai" ? "🤖 AI 生成" : t === "episodes" ? "📺 剧集" : t === "characters" ? "🎭 角色" : "⚙️ 项目设置"}
          </button>
        ))}
      </div>

      {tab === "ai" && <AIGenPanel project={project} onChange={load} onError={setError} />}
      {tab === "characters" && <CharacterPanel project={project} onChange={load} onError={setError} />}
      {tab === "episodes" && <EpisodePanel project={project} onChange={load} onError={setError} />}
      {tab === "settings" && <ProjectSettings project={project} onChange={load} onError={setError} />}
    </div>
  );
}

/* ── AI 生成面板 ─────────────────────────────────────── */

type AIGenStep = "setup" | "outline" | "dialogues";

function AIGenPanel({ project, onChange, onError }: {
  project: Project; onChange: () => void; onError: (m: string) => void;
}) {
  // 如果项目已有剧集摘要，初始直接进入 Step2 编辑大纲
  const hasExistingOutline = project.episodes.length > 0 && project.episodes.some(e => e.summary);
  const [step, setStep] = useState<AIGenStep>(hasExistingOutline ? "outline" : "setup");
  const [description, setDescription] = useState("");
  const [extra, setExtra] = useState("");
  const [numEpisodes, setNumEpisodes] = useState(6);
  const [targetDuration, setTargetDuration] = useState(25);
  const [narrationRatio, setNarrationRatio] = useState(50);
  const estLines = Math.max(10, targetDuration * 60 / 4);
  const [loading, setLoading] = useState(false);
  const [storyArc, setStoryArc] = useState("");
  const [outlineDraft, setOutlineDraft] = useState<Array<{ id: string; title: string; summary: string }>>([]);
  const [genDialoguesFor, setGenDialoguesFor] = useState<string[]>([]);
  const [selectAllEpisodes, setSelectAllEpisodes] = useState(false);

  // 检查剧集是否已有对白
  const hasDialogues = (epId: string) => {
    const ep = project.episodes.find(e => e.id === epId);
    return ep && ep.dialogues && ep.dialogues.length > 0;
  };

  // 已有剧集时，初始化 outlineDraft
  useEffect(() => {
    if (hasExistingOutline && outlineDraft.length === 0) {
      setOutlineDraft(
        project.episodes
          .filter(e => e.summary)
          .map(e => ({ id: e.id, title: e.title, summary: e.summary }))
      );
    }
  }, [hasExistingOutline, project.episodes]);

  // 步骤1：生成完整大纲
  const generateOutline = async () => {
    if (!description.trim()) { onError("请输入故事描述"); return; }
    setLoading(true);
    onError("");
    try {
      const r = await api.generateEpisodes(project.id, description, numEpisodes, extra);
      // 如果 LLM 返回了故事标题，自动更新项目名
      if (r.story_title && r.story_title !== project.name) {
        await api.updateProject(project.id, r.story_title);
      }
      setStoryArc(r.story_arc || "");
      // 直接从 API 获取最新项目数据，确保拿到新生成的剧集
      const updated = await api.getProject(project.id);
      const freshDraft = r.episode_ids.map((id: string, i: number) => {
        const ep = updated.episodes.find(e => e.id === id);
        return {
          id,
          title: ep?.title || `第${i + 1}集`,
          summary: ep?.summary || "",
        };
      });
      setOutlineDraft(freshDraft);
      onChange();
      setStep("outline");
      onError(`✅ 已生成 ${r.created} 集大纲`);
    } catch (e: any) {
      onError(e.message);
    }
    setLoading(false);
  };

  // 步骤2：编辑大纲后批量生成对白
  const generateAllDialogues = async () => {
    setLoading(true);
    onError("");
    const epsToGen = genDialoguesFor.length > 0 ? genDialoguesFor : (selectAllEpisodes ? outlineDraft.map(e => e.id) : []);
    const errors: string[] = [];
    for (const epId of epsToGen) {
      try {
        await api.generateDialogues(project.id, epId, "", targetDuration, narrationRatio);
      } catch (e: any) {
        errors.push(e.message);
      }
    }
    onChange();
    setStep("outline");
    if (errors.length > 0) {
      onError(`✅ 已提交 ${epsToGen.length - errors.length} 集生成任务（${errors.length} 集失败，请重试）`);
    } else {
      onError(`✅ 已提交 ${epsToGen.length} 集生成任务，后台处理中`);
    }
    setLoading(false);
  };

  const updateOutlineItem = (id: string, field: "title" | "summary", value: string) => {
    setOutlineDraft(prev => prev.map(item =>
      item.id === id ? { ...item, [field]: value } : item
    ));
  };

  const saveOutline = async () => {
    setLoading(true);
    try {
      for (const item of outlineDraft) {
        await api.updateEpisode(project.id, item.id, { title: item.title, summary: item.summary });
      }
      onChange();
      onError("✅ 大纲已保存");
    } catch (e: any) {
      onError(e.message);
    }
    setLoading(false);
  };

  const removeOutlineItem = (id: string) => {
    setOutlineDraft(prev => prev.filter(item => item.id !== id));
  };

  const [regenDescription, setRegenDescription] = useState("");
  const [regenExtra, setRegenExtra] = useState("");
  const [regenNum, setRegenNum] = useState(6);
  // 当前展开重生表单的 episode id，null 表示没有展开
  const [regenOpenId, setRegenOpenId] = useState<string | null>(null);

  // 某张卡片点击「从本章重生」
  const openRegenForm = (episodeId: string, episodeIndex: number) => {
    const episodesAfter = outlineDraft.length - (episodeIndex + 1);
    const confirmMsg =
      `⚠️ 不可逆操作！\n\n` +
      `将从第 ${episodeIndex + 1} 集开始重新生成后续大纲。\n` +
      `第 ${episodeIndex + 2} 集及之后的 ${episodesAfter} 集将被永久删除，\n` +
      `包括所有旁白、对白文本和已生成的音频文件。\n\n` +
      `确定要继续吗？`;
    if (!window.confirm(confirmMsg)) return;
    setRegenOpenId(episodeId);
  };

  // 取消重生表单
  const cancelRegenForm = () => {
    setRegenOpenId(null);
    setRegenDescription("");
    setRegenExtra("");
  };

  // 执行重新生成大纲（不可逆操作：废弃后续所有剧集及其音频/对白）
  const regenerateFrom = async () => {
    if (!regenOpenId) return;
    const desc = regenDescription.trim();
    const ext = regenExtra.trim();
    setLoading(true);
    onError("");
    try {
      const r = await api.regenerateFrom(project.id, regenOpenId, desc, regenNum, ext);
      if (r.story_title && r.story_title !== project.name) {
        await api.updateProject(project.id, r.story_title);
      }
      const updated = await api.getProject(project.id);
      const allEps = updated.episodes.filter((e: any) => e.summary);
      setOutlineDraft(allEps.map((e: any) => ({ id: e.id, title: e.title, summary: e.summary })));
      setGenDialoguesFor([]);
      setStoryArc(r.story_arc || "");
      setRegenOpenId(null);
      setRegenDescription("");
      setRegenExtra("");
      setStep("outline");
      onChange();
      onError(`✅ 已重新生成 ${r.created} 集大纲，废弃了 ${r.deleted} 集旧剧集（含音频文件）`);
    } catch (e: any) {
      onError(e.message);
    }
    setLoading(false);
  };

  // 从 LLM 生成的标题中去掉"第X集"前缀，保留书名号和其余内容
  const cleanTitle = (t: string) => t.replace(/^第\s*\d+\s*集\s*/, "").trim();

  const arcColors: Record<string, string> = {
    "铺垫": "#3b82f6",
    "发展": "#a855f7",
    "高潮": "#ef4444",
    "结局": "#22c55e",
    "完整故事线": "#f59e0b",
  };

  const getArcColor = (summary: string) => {
    const m = summary.match(/^\[(\w+)\]/);
    return m ? arcColors[m[1]] || "#64748b" : "#64748b";
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      {/* 步骤指示器 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        {(["setup", "outline", "dialogues"] as AIGenStep[]).map((s, i) => (
          <div key={s} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {i > 0 && <div style={{ width: 24, height: 1, background: "#334155" }} />}
            <div style={{
              padding: "6px 14px",
              borderRadius: 20,
              fontSize: 13,
              fontWeight: 600,
              background: step === s ? "#a855f7" : "#1e293b",
              color: step === s ? "#fff" : "#64748b",
              border: `1px solid ${step === s ? "#a855f7" : "#334155"}`,
            }}>
              {i + 1}. {s === "setup" ? "故事设定" : s === "outline" ? "编辑大纲" : "生成对白"}
            </div>
          </div>
        ))}
      </div>

      {/* 步骤1：故事设定 */}
      {step === "setup" && (
        <div style={{ display: "grid", gap: 12 }}>
          {/* 如果已有大纲，提供修改剧情入口 */}
          {hasExistingOutline && (
            <div style={{
              background: "linear-gradient(135deg, #1c1917 0%, #0f1117 100%)",
              border: "1px solid #78350f",
              borderRadius: 8,
              padding: 16,
              display: "grid",
              gap: 12,
            }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontSize: 14, color: "#fbbf24", fontWeight: 600 }}>📖 已有 {project.episodes.length} 集大纲</div>
                  <div style={{ fontSize: 12, color: "#92400e", marginTop: 2 }}>
                    可以修改标题/摘要后重新生成对白，或从某一集开始重新生成剧情
                  </div>
                </div>
                <button
                  onClick={() => {
                    // 初始化 outlineDraft 然后跳到编辑大纲
                    setOutlineDraft(
                      project.episodes
                        .filter(e => e.summary)
                        .map(e => ({ id: e.id, title: e.title, summary: e.summary }))
                    );
                    setStep("outline");
                  }}
                  style={{
                    padding: "8px 20px",
                    background: "#f59e0b",
                    color: "#1c1917",
                    border: "none",
                    borderRadius: 8,
                    cursor: "pointer",
                    fontWeight: 700,
                    fontSize: 13,
                  }}
                >
                  ✏️ 编辑大纲 / 修改剧情
                </button>
              </div>
            </div>
          )}

          <div style={{ background: "#0f1117", border: "1px solid #1e293b", borderRadius: 8, padding: 16, display: "grid", gap: 12 }}>
            <div>
              <label style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4, display: "block" }}>故事描述 *</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="描述你的故事背景、主要角色、剧情走向、风格基调...&#10;&#10;例如：一个关于高中生小明和小红的校园成长故事，从相识到面对高考的挑战，风格温暖治愈。"
                rows={5}
                style={{ ...inputMd, width: "100%", resize: "vertical" }}
              />
            </div>
            <div>
              <label style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4, display: "block" }}>额外要求（可选）</label>
              <input
                value={extra}
                onChange={(e) => setExtra(e.target.value)}
                placeholder="如：每集结尾要有悬念、加入搞笑元素、侧重心理描写..."
                style={{ ...inputMd, width: "100%" }}
              />
            </div>
            <div style={{ display: "flex", gap: 12 }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: 12, color: "#94a3b8", marginBottom: 4, display: "block" }}>总集数</label>
                <input
                  type="number"
                  value={numEpisodes}
                  onChange={(e) => setNumEpisodes(Math.max(1, parseInt(e.target.value) || 3))}
                  min={1}
                  style={{ ...inputMd, width: 80 }}
                />
              </div>
            </div>

            {project.characters.length > 0 && (
              <div style={{ fontSize: 12, color: "#64748b" }}>
                🎭 已有角色: {project.characters.map(c => c.name).join(", ")}
              </div>
            )}
            {project.episodes.length > 0 && (
              <div style={{ fontSize: 12, color: "#f59e0b" }}>
                ⚠️ 项目中已有 {project.episodes.length} 集，继续生成会追加新剧集
              </div>
            )}

            <button
              onClick={generateOutline}
              disabled={loading}
              style={{
                padding: "10px 24px",
                background: loading ? "#334155" : "#a855f7",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: loading ? "wait" : "pointer",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {loading ? "⏳ 生成大纲中..." : "📝 生成完整大纲"}
            </button>
          </div>
        </div>
      )}

      {/* 步骤2：编辑大纲 */}
      {step === "outline" && (
        <div style={{ display: "grid", gap: 12 }}>
          {storyArc && (
            <div style={{
              background: "linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%)",
              border: "1px solid #312e81",
              borderRadius: 8,
              padding: "12px 16px",
            }}>
              <div style={{ fontSize: 11, color: "#818cf8", marginBottom: 4 }}>📖 故事弧线</div>
              <div style={{ fontSize: 14, color: "#c7d2fe", fontWeight: 600 }}>{storyArc}</div>
            </div>
          )}

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: 13, color: "#94a3b8" }}>
              共 {outlineDraft.length} 集，可编辑标题和摘要
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={() => setStep("setup")} style={btnGhost}>← 返回修改</button>
              <button onClick={saveOutline} disabled={loading} style={{ ...btnGhost, color: "#3b82f6", borderColor: "#3b82f6" }}>
                💾 保存大纲
              </button>
              <button onClick={() => {
                    // 自动勾选前3个未生成对白的剧集
                    const noDlg = outlineDraft.filter(item => !hasDialogues(item.id));
                    setGenDialoguesFor(noDlg.slice(0, 3).map(e => e.id));
                    setSelectAllEpisodes(false);
                    setStep("dialogues");
                }} style={{ ...btnGhost, color: "#22c55e", borderColor: "#22c55e" }}>
                💬 确认并生成对白 →
              </button>
            </div>
          </div>

          {outlineDraft.map((item, i) => (
            <div key={item.id} style={{
              background: "#0f1117",
              border: `1px solid ${getArcColor(item.summary)}33`,
              borderRadius: 8,
              padding: 12,
              display: "grid",
              gap: 8,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{
                  padding: "2px 8px",
                  borderRadius: 4,
                  fontSize: 11,
                  fontWeight: 600,
                  background: getArcColor(item.summary) + "22",
                  color: getArcColor(item.summary),
                }}>
                  {item.summary.match(/^\[(\w+)\]/)?.[1] || "集"} {i + 1}
                </span>
                <input
                  value={cleanTitle(item.title)}
                  onChange={(e) => updateOutlineItem(item.id, "title", e.target.value)}
                  style={{ ...inputMd, flex: 1, fontWeight: 600 }}
                />
                {i < outlineDraft.length - 1 && (
                  <button
                    onClick={() => openRegenForm(item.id, i)}
                    disabled={loading}
                    style={{
                      background: "transparent", border: "1px solid #78350f", color: "#f59e0b",
                      cursor: "pointer", fontSize: 11, padding: "2px 8px", borderRadius: 4,
                      fontWeight: 600,
                    }}
                    title="从本章开始重新生成后续大纲（不可逆：将删除本章之后所有剧集、对白和音频文件）"
                  >🔄 从本章重生</button>
                )}
                <button
                  onClick={() => removeOutlineItem(item.id)}
                  style={{ background: "transparent", border: "none", color: "#475569", cursor: "pointer", fontSize: 16 }}
                  title="删除此集"
                >×</button>
              </div>
              <textarea
                value={item.summary.replace(/^\[(\w+)\]\s*/, "")}
                onChange={(e) => {
                  const phase = item.summary.match(/^\[(\w+)\]/)?.[1] || "";
                  updateOutlineItem(item.id, "summary", phase ? `[${phase}] ${e.target.value}` : e.target.value);
                }}
                rows={3}
                style={{ ...inputMd, width: "100%", resize: "vertical", fontSize: 12 }}
                placeholder="编辑剧集摘要..."
              />

              {/* 内联重生表单：展开在当前卡片下方 */}
              {regenOpenId === item.id && (
                <div style={{
                  marginTop: 4,
                  padding: 12,
                  background: "#1c1917",
                  border: "1px solid #78350f",
                  borderRadius: 6,
                  display: "grid",
                  gap: 8,
                }}>
                  <div style={{ fontSize: 12, color: "#fbbf24", fontWeight: 600 }}>
                    🔄 从第 {i + 1} 集《{cleanTitle(item.title)}》重生后续剧情
                  </div>
                  <div style={{ fontSize: 11, color: "#92400e" }}>
                    ⚠️ 后续 {outlineDraft.length - i - 1} 集的所有内容（含音频）将被永久删除
                  </div>
                  <div>
                    <label style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2, display: "block" }}>
                      后续走向（可选，留空则基于前情自动续写）
                    </label>
                    <textarea
                      value={regenDescription}
                      onChange={(e) => setRegenDescription(e.target.value)}
                      placeholder="在原有故事主线上微调后续走向，例如：主角发现真相后黑化，与好友反目成仇..."
                      rows={3}
                      style={{ ...inputMd, width: "100%", resize: "vertical", fontSize: 12 }}
                    />
                  </div>
                  <div style={{ display: "flex", gap: 8 }}>
                    <div style={{ flex: 1 }}>
                      <label style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2, display: "block" }}>额外要求（可选）</label>
                      <input
                        value={regenExtra}
                        onChange={(e) => setRegenExtra(e.target.value)}
                        placeholder="如：增加悬疑元素、感情线为主..."
                        style={{ ...inputMd, width: "100%", fontSize: 12 }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: 11, color: "#94a3b8", marginBottom: 2, display: "block" }}>生成集数</label>
                      <input
                        type="number"
                        value={regenNum}
                        onChange={(e) => setRegenNum(Math.max(1, parseInt(e.target.value) || 3))}
                        min={1}
                        style={{ ...inputMd, width: 60 }}
                      />
                    </div>
                  </div>
                  <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                    <button
                      onClick={cancelRegenForm}
                      disabled={loading}
                      style={{ ...btnGhost }}
                    >取消</button>
                    <button
                      onClick={regenerateFrom}
                      disabled={loading}
                      style={{
                        padding: "6px 16px",
                        background: loading ? "#78350f" : "#f59e0b",
                        color: loading ? "#a8a29e" : "#1c1917",
                        border: "none",
                        borderRadius: 6,
                        cursor: loading ? "wait" : "pointer",
                        fontWeight: 700,
                        fontSize: 13,
                      }}
                    >
                      {loading ? "⏳ 生成中..." : "⚠️ 确认重生"}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 步骤3：生成对白 */}
      {step === "dialogues" && (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{
            background: "#0f1117",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: 16,
          }}>
            <div style={{ fontSize: 14, color: "#e2e8f0", marginBottom: 8 }}>
              将为以下 <strong>{outlineDraft.length}</strong> 集生成旁白+对白：
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
              <span style={{ fontSize: 13, color: "#94a3b8" }}>选择剧集</span>
              <button onClick={() => { setSelectAllEpisodes(true); setGenDialoguesFor(outlineDraft.map(e => e.id)); }}
                style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, border: "1px solid #475569", color: "#94a3b8", background: "transparent", cursor: "pointer" }}>
                全选
              </button>
              <button onClick={() => { setSelectAllEpisodes(false); setGenDialoguesFor([]); }}
                style={{ fontSize: 11, padding: "2px 8px", borderRadius: 4, border: "1px solid #475569", color: "#94a3b8", background: "transparent", cursor: "pointer" }}>
                清除
              </button>
              {genDialoguesFor.length > 0 && (
                <span style={{ fontSize: 11, color: "#475569" }}>已选 {genDialoguesFor.length} 集</span>
              )}
            </div>
            <div style={{ display: "grid", gap: 4 }}>
              {outlineDraft.map((item, i) => {
                const hasDlg = hasDialogues(item.id);
                const isChecked = selectAllEpisodes || genDialoguesFor.includes(item.id);
                return (
                <label key={item.id} style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "4px 8px",
                  borderRadius: 4,
                  background: isChecked ? "transparent" : "#1e293b",
                  cursor: "pointer",
                  opacity: !selectAllEpisodes && genDialoguesFor.length > 0 && !genDialoguesFor.includes(item.id) ? 0.4 : 1,
                }}>
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={(e) => {
                      if (selectAllEpisodes) {
                        // 从全选状态切换：先退出全选，再处理当前项
                        setSelectAllEpisodes(false);
                        setGenDialoguesFor(outlineDraft.map(e => e.id).filter(id => id !== item.id));
                      } else {
                        if (e.target.checked) {
                          setGenDialoguesFor(prev => [...prev, item.id]);
                        } else {
                          setGenDialoguesFor(prev => prev.filter(id => id !== item.id));
                        }
                      }
                    }}
                    style={{ accentColor: "#a855f7" }}
                  />
                  <span style={{ fontSize: 12, color: "#94a3b8" }}>{i + 1}</span>
                  <span style={{ fontSize: 13, color: "#e2e8f0" }}>{cleanTitle(item.title)}</span>
                  {hasDlg && (
                    <span style={{ fontSize: 10, color: "#22c55e", border: "1px solid #22c55e", borderRadius: 3, padding: "0 4px" }}>已生成</span>
                  )}
                  <span style={{ fontSize: 11, color: "#475569", marginLeft: "auto" }}>
                    {item.summary.replace(/^\[(\w+)\]\s*/, "").slice(0, 40)}...
                  </span>
                </label>
              );})}
            </div>
          </div>

          {/* 生成参数 */}
          <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", padding: "8px 0", borderTop: "1px solid #1e293b" }}>
            <div>
              <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 2 }}>每集时长（分钟）</label>
              <input
                type="number"
                value={targetDuration}
                onChange={(e) => setTargetDuration(Math.max(1, Math.min(120, parseInt(e.target.value) || 25)))}
                min={1}
                max={120}
                style={{ ...inputMd, width: 70, fontSize: 13 }}
              />
            </div>
            <div style={{ minWidth: 160 }}>
              <label style={{ fontSize: 11, color: "#64748b", display: "block", marginBottom: 2 }}>{'旁白 ' + narrationRatio + '% / 对话 ' + (100 - narrationRatio) + '%'}</label>
              <input
                type="range"
                min={0}
                max={100}
                step={10}
                value={narrationRatio}
                onChange={(e) => setNarrationRatio(parseInt(e.target.value))}
                style={{ width: "100%", accentColor: "#a78bfa" }}
              />
            </div>
            <div style={{ fontSize: 11, color: "#475569", paddingBottom: 4 }}>
              {"≈ " + estLines + " lines/ep"}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => setStep("outline")} style={btnGhost}>← 返回编辑大纲</button>
            <button
              onClick={generateAllDialogues}
              disabled={loading}
              style={{
                padding: "10px 24px",
                background: loading ? "#334155" : "#22c55e",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                cursor: loading ? "wait" : "pointer",
                fontWeight: 600,
                fontSize: 14,
              }}
            >
              {loading ? "⏳ 生成中..." : "🚀 批量生成旁白+对白"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

const btnGhost: React.CSSProperties = {
  background: "transparent", color: "#94a3b8", border: "1px solid #334155",
  borderRadius: 6, padding: "4px 12px", cursor: "pointer", fontSize: 13,
};
const btnTab: React.CSSProperties = {
  padding: "8px 20px", background: "transparent", color: "#64748b",
  border: "1px solid #334155", borderRadius: 8, cursor: "pointer", fontSize: 14,
};
const btnTabActive: React.CSSProperties = {
  ...btnTab, background: "#1e293b", color: "#3b82f6", borderColor: "#3b82f6",
};
const errorBox: React.CSSProperties = {
  background: "#7f1d1d", color: "#fca5a5", padding: "8px 12px",
  borderRadius: 6, marginBottom: 12,
};
const successBox: React.CSSProperties = {
  background: "#14532d", color: "#86efac", padding: "8px 12px",
  borderRadius: 6, marginBottom: 12,
};
const inputMd: React.CSSProperties = {
  padding: "8px 12px", background: "#1e293b", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0", fontSize: 13, outline: "none",
};
