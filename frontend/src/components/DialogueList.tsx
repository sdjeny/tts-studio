import { useState } from "react";
import { api, Project, Episode, Dialogue, Character } from "../api";

/** 根据角色名生成稳定颜色 */
function stringToColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  const colors = ["#f472b6", "#a78bfa", "#60a5fa", "#34d399", "#fbbf24", "#fb923c", "#f87171", "#38bdf8"];
  return colors[Math.abs(hash) % colors.length];
}

export default function DialogueList({ project, episode, onChange, onError }: {
  project: Project; episode: Episode; onChange: () => void; onError: (m: string) => void;
}) {
  const [adding, setAdding] = useState(false);
  const [charId, setCharId] = useState(project.characters[0]?.id || "");
  const [text, setText] = useState("");
  const [instruct, setInstruct] = useState("");
  const [bulk, setBulk] = useState(false);
  const [bulkText, setBulkText] = useState("");

  const add = async () => {
    if (!text.trim() || !charId) return;
    try {
      await api.addDialogue(project.id, episode.id, { character_id: charId, text: text.trim(), instruct: instruct.trim() });
      setText(""); setInstruct(""); setAdding(false);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const addBulk = async () => {
    if (!bulkText.trim() || !charId) return;
    const lines = bulkText.split("\n").filter(l => l.trim());
    if (lines.length === 0) return;
    try {
      await api.batchAddDialogues(project.id, episode.id,
        lines.map(l => ({ character_id: charId, text: l.trim(), instruct: instruct.trim() })));
      setBulkText(""); setAdding(false); setBulk(false);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const generate = async (dlgId: string) => {
    try {
      await api.generateAudio(project.id, episode.id, dlgId);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const clearHistory = async (dlgId: string) => {
    if (!confirm("清空该对白的音频历史？")) return;
    try {
      await api.clearAudioHistory(project.id, episode.id, dlgId);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const download = (dlgId: string, audioId: string) => {
    window.open(api.downloadAudio(project.id, episode.id, dlgId, audioId), "_blank");
  };

  const activateAudio = async (dlgId: string, audioId: string) => {
    try {
      await api.setCurrentAudio(project.id, episode.id, dlgId, audioId);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const removeAudio = async (dlgId: string, audioId: string) => {
    if (!confirm("删除该条音频历史？")) return;
    try {
      await api.removeAudio(project.id, episode.id, dlgId, audioId);
      onChange();
    } catch (e: any) { onError(e.message); }
  };

  const sorted = [...(episode.dialogues || [])].sort((a, b) => a.order - b.order);

  return (
    <div>
      {/* 对白列表 */}
      {sorted.length === 0 && !adding ? (
        <p style={{ color: "#64748b", textAlign: "center", padding: 20 }}>暂无旁白/对白</p>
      ) : (
        <div style={{ display: "grid", gap: 6, marginBottom: 12 }}>
          {sorted.map((dlg, idx) => (
            <DialogueRow
              key={dlg.id}
              dlg={dlg}
              index={idx}
              onGenerate={() => generate(dlg.id)}
              onClearHistory={() => clearHistory(dlg.id)}
              onDownload={(audioId) => download(dlg.id, audioId)}
              onActivate={(audioId) => activateAudio(dlg.id, audioId)}
              onRemoveAudio={(audioId) => removeAudio(dlg.id, audioId)}
              onDelete={async () => {
                const audioCount = dlg.audio_history?.length || 0;
                const msg = audioCount > 0
                  ? `⚠️ 不可逆操作！\n\n将删除该条对白及其所有 ${audioCount} 个音频文件（磁盘文件一并删除）。\n\n确定要继续吗？`
                  : "确定删除该条对白？";
                if (!confirm(msg)) return;
                await api.purgeDialogue(project.id, episode.id, dlg.id);
                onChange();
              }}
              onUpdate={async (data) => {
                await api.updateDialogue(project.id, episode.id, dlg.id, data);
                onChange();
              }}
              characters={project.characters}
            />
          ))}
        </div>
      )}

      {/* 添加表单 */}
      {adding ? (
        <div style={{ background: "#0f1117", border: "1px solid #334155", borderRadius: 8, padding: 12 }}>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <select value={charId} onChange={(e) => setCharId(e.target.value)} style={{ ...inputSm, minWidth: 120 }}>
              <option value="__旁白__">📖 旁白</option>
              <option value="__场景__">🎬 场景</option>
              {project.characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, color: "#94a3b8" }}>
              <input type="checkbox" checked={bulk} onChange={(e) => setBulk(e.target.checked)} />
              批量
            </label>
          </div>
          {bulk ? (
            <textarea
              value={bulkText} onChange={(e) => setBulkText(e.target.value)}
              placeholder="每行一条..." rows={5}
              style={{ ...inputSm, width: "100%", resize: "vertical", minHeight: 80 }}
            />
          ) : (
            <textarea
              value={text} onChange={(e) => setText(e.target.value)}
              placeholder="输入内容..." rows={3}
              style={{ ...inputSm, width: "100%", resize: "vertical" }}
            />
          )}
          <input
            value={instruct} onChange={(e) => setInstruct(e.target.value)}
            placeholder="instruct（如：低沉缓慢、紧张、欢快）"
            style={{ ...inputSm, width: "100%", marginTop: 6 }}
          />
          <div style={{ display: "flex", gap: 6, marginTop: 8 }}>
            <button onClick={bulk ? addBulk : add} style={btnBlue}>确认添加</button>
            <button onClick={() => { setAdding(false); setBulk(false); }} style={btnGhost}>取消</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...btnGhost, width: "100%", padding: "8px" }}>
          + 添加旁白/对白/场景
        </button>
      )}
    </div>
  );
}

/* ── 单条行 ─────────────────────────────────────── */

function DialogueRow({ dlg, index, onGenerate, onClearHistory, onDownload, onDelete, onUpdate, onActivate, onRemoveAudio, characters }: {
  dlg: Dialogue; index: number;
  onGenerate: () => void; onClearHistory: () => void;
  onDownload: (audioId: string) => void;
  onDelete: () => void;
  onUpdate: (data: { character_id?: string; text?: string; instruct?: string }) => void;
  onActivate: (audioId: string) => void;
  onRemoveAudio: (audioId: string) => void;
  characters: Character[];
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState(dlg.text);
  const [editCharId, setEditCharId] = useState(dlg.character_id);
  const [editInstruct, setEditInstruct] = useState(dlg.instruct || "");
  const [showHistory, setShowHistory] = useState(false);

  const currentAudio = dlg.audio_history?.find(a => a.id === dlg.current_audio_id);

  const isNarrator = dlg.character_name === "旁白";
  const isScene = dlg.character_name === "场景";

  const statusColors: Record<string, string> = {
    pending: "#64748b", generating: "#f59e0b", completed: "#22c55e", failed: "#ef4444",
  };
  const statusLabels: Record<string, string> = {
    pending: "待生成", generating: "生成中...", completed: "已完成", failed: "失败",
  };

  // 不同类型的卡片样式
  const rowBg = isNarrator ? "#0c1222" : isScene ? "#1a1a0e" : "#0f1117";
  const rowBorder = isNarrator ? "#1e3a5f" : isScene ? "#5c4b00" : "#1e293b";

  return (
    <div style={{ background: rowBg, border: `1px solid ${rowBorder}`, borderRadius: 8, padding: "10px 14px" }}>
      {/* 头部 */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <span style={{ color: "#475569", fontSize: 12, minWidth: 24 }}>#{index + 1}</span>

        {isScene ? (
          <span style={tagStyle("#eab308")}>🎬 场景</span>
        ) : isNarrator ? (
          <span style={tagStyle("#60a5fa")}>📖 旁白</span>
        ) : (
          <select value={editCharId} onChange={(e) => { setEditCharId(e.target.value); onUpdate({ character_id: e.target.value }); }}
            style={{ ...inputSm, padding: "2px 6px", fontSize: 12, width: "auto", minWidth: 80 }}>
            <option value="__旁白__">📖 旁白</option>
            <option value="__场景__">🎬 场景</option>
            {characters.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            {editCharId && editCharId !== "__旁白__" && editCharId !== "__场景__" && !characters.find(c => c.id === editCharId) && (
              <option value={editCharId}>⚠ 异常({editCharId.slice(0, 8)})</option>
            )}
          </select>
        )}

        <span style={{ color: statusColors[dlg.status] || "#64748b", fontSize: 11 }}>
          ● {statusLabels[dlg.status] || dlg.status}
        </span>
        {dlg.audio_history?.length > 0 && (
          <span style={{ color: "#475569", fontSize: 11 }}>({dlg.audio_history.length} 条历史)</span>
        )}
      </div>

      {/* 内容 */}
      {editing ? (
        <div style={{ marginBottom: 8 }}>
          {dlg.summary && (
            <div style={{ fontSize: 11, color: isScene ? "#eab308" : "#a855f7", marginBottom: 4, fontStyle: "italic" }}>
              📋 {dlg.summary}
            </div>
          )}
          <textarea value={editText} onChange={(e) => setEditText(e.target.value)}
            style={{ ...inputSm, width: "100%", resize: "vertical", minHeight: 60 }} />
          <input value={editInstruct} onChange={(e) => setEditInstruct(e.target.value)}
            placeholder="instruct（如：低沉缓慢、紧张、欢快）"
            style={{ ...inputSm, width: "100%", marginTop: 4 }} />
          <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
            <button onClick={() => { onUpdate({ text: editText, instruct: editInstruct }); setEditing(false); }}
              style={{ ...btnBlue, padding: "3px 10px", fontSize: 12 }}>保存</button>
            <button onClick={() => setEditing(false)} style={{ ...btnGhost, padding: "3px 10px", fontSize: 12 }}>取消</button>
          </div>
        </div>
      ) : (
        <>
          {dlg.summary && (
            <div style={{ fontSize: 11, color: isScene ? "#eab308" : "#a855f7", marginBottom: 4, fontStyle: "italic" }}>
              📋 {dlg.summary}
            </div>
          )}
          {isScene ? (
            <div style={{
              fontSize: 13, lineHeight: 1.8, marginBottom: 4, whiteSpace: "pre-wrap",
              color: "#fde68a", fontStyle: "italic", padding: "8px 12px",
              background: "#5c4b0015", borderRadius: 4, borderLeft: "3px solid #eab308",
            }}>
              🎬 {dlg.text}
            </div>
          ) : isNarrator ? (
            <div style={{
              fontSize: 14, lineHeight: 1.9, marginBottom: 4, whiteSpace: "pre-wrap",
              color: "#bfdbfe", padding: "8px 12px",
              background: "#1e3a5f15", borderRadius: 4, borderLeft: "3px solid #60a5fa",
            }}>
              {dlg.text}
            </div>
          ) : (
            <div style={{
              fontSize: 14, lineHeight: 1.7, marginBottom: 4, whiteSpace: "pre-wrap",
              color: "#e2e8f0", padding: "8px 12px",
              background: stringToColor(dlg.character_name) + "08",
              borderRadius: 4, borderLeft: `3px solid ${stringToColor(dlg.character_name)}`,
            }}>
              <span style={{ color: stringToColor(dlg.character_name), fontWeight: 700 }}>{dlg.character_name}：</span>
              {dlg.text}
            </div>
          )}
          {dlg.instruct && (
            <div style={{ fontSize: 12, color: "#64748b", marginBottom: 8, fontStyle: "italic" }}>
              💬 {dlg.instruct}
            </div>
          )}
        </>
      )}

      {/* 操作栏 */}
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
        {dlg.status !== "generating" ? (
          <button onClick={onGenerate} style={{ ...btnBlue, padding: "3px 10px", fontSize: 12 }}>
            {currentAudio ? "🔄 重新生成" : "🔊 生成音频"}
          </button>
        ) : dlg.audio_history?.some(a => a.status === "generating" && a.interrupted) ? (
          <span style={{ color: "#f97316", fontSize: 12 }}>⚡ 中断，点击刷新重试</span>
        ) : (
          <span style={{ color: "#f59e0b", fontSize: 12 }}>⏳ 生成中...</span>
        )}

        {currentAudio && (
          <>
            <audio controls src={currentAudio.url} style={{ height: 28, maxWidth: 200 }} />
            {currentAudio.duration != null && currentAudio.duration > 0 && (
              <span style={{ color: "#64748b", fontSize: 11, minWidth: 36 }}>{currentAudio.duration.toFixed(1)}s</span>
            )}
          </>
        )}


        {dlg.audio_history?.length > 0 && (
          <button onClick={() => setShowHistory(!showHistory)} style={{ ...btnGhost, padding: "3px 8px", fontSize: 12 }}>
            📜 历史 ({dlg.audio_history.length})
          </button>
        )}

        <div style={{ flex: 1 }} />

        <button onClick={() => setEditing(true)} style={{ ...btnGhost, padding: "3px 8px", fontSize: 12 }}>✏️</button>
        <button onClick={onClearHistory} style={{ ...btnGhost, padding: "3px 8px", fontSize: 12, color: "#f59e0b", borderColor: "#f59e0b" }}>清空历史</button>
        <button onClick={onDelete} style={{ ...btnGhost, padding: "3px 8px", fontSize: 12, color: "#ef4444", borderColor: "#ef4444" }} title="清空对白及音频文件">🗑</button>
      </div>

      {/* 历史列表 */}
      {showHistory && dlg.audio_history?.length > 0 && (
        <div style={{ marginTop: 8, borderTop: "1px solid #1e293b", paddingTop: 8, display: "grid", gap: 4 }}>
          {[...dlg.audio_history].reverse().map((ah, i) => (
            <div key={ah.id} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#94a3b8" }}>
              <span>{dlg.audio_history.length - i}.</span>
              <span style={{ color: "#64748b", fontSize: 10, minWidth: 80 }}>{ah.id.slice(0, 8)}</span>
              <span style={{ color: "#64748b", fontSize: 10, minWidth: 72 }}>{ah.created_at?.slice(0, 19)}</span>
              {ah.duration != null && ah.duration > 0 && (
                <span style={{ color: "#64748b", fontSize: 10 }}>{ah.duration.toFixed(1)}s</span>
              )}
              {ah.url ? (
                <>
                  <audio controls src={ah.url} style={{ height: 24, maxWidth: 140 }} />
                  <button onClick={() => onDownload(ah.id)} style={{ ...btnGhost, padding: "1px 6px", fontSize: 11 }}>⬇</button>
                </>
              ) : ah.status === "generating" ? (
                ah.interrupted ? (
                  <span style={{ color: "#f97316", fontSize: 11, fontStyle: "italic" }}>⚡ 中断，点击刷新重试{ah.error ? ` (${ah.error})` : ""}</span>
                ) : (
                  <span style={{ color: "#f59e0b", fontSize: 11, fontStyle: "italic" }}>⏳ 生成中...</span>
                )
              ) : (
                <span style={{ color: "#ef4444", fontSize: 11, fontStyle: "italic" }}>❌ {ah.error || "生成失败"}</span>
              )}
              {ah.raw ? (
                <span style={{ color: "#64748b", fontSize: 10, fontStyle: "italic" }}>原始</span>
              ) : (
                <span style={{ color: "#a78bfa", fontSize: 10 }}>已音效</span>
              )}
              {ah.id === dlg.current_audio_id ? (
                <span style={{ color: "#22c55e", fontSize: 11 }}>✓ 起效</span>
              ) : ah.url ? (
                <button onClick={() => onActivate(ah.id)} style={{ ...btnGhost, padding: "1px 6px", fontSize: 11, color: "#3b82f6", borderColor: "#3b82f6" }}>起效</button>
              ) : null}
              <button onClick={() => onRemoveAudio(ah.id)} style={{ ...btnGhost, padding: "1px 6px", fontSize: 11, color: "#ef4444", borderColor: "#ef4444" }}>✕</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function tagStyle(color: string): React.CSSProperties {
  return {
    padding: "2px 8px", borderRadius: 4, fontSize: 12, fontWeight: 600,
    background: color + "22", color,
  };
}

const inputSm: React.CSSProperties = {
  padding: "5px 8px", background: "#1e293b", border: "1px solid #334155",
  borderRadius: 4, color: "#e2e8f0", fontSize: 13, outline: "none",
};
const btnBlue: React.CSSProperties = {
  background: "#3b82f6", color: "#fff", border: "none",
  borderRadius: 4, cursor: "pointer", fontWeight: 600,
};
const btnGhost: React.CSSProperties = {
  background: "transparent", color: "#94a3b8",
  border: "1px solid #334155", borderRadius: 4,
  cursor: "pointer", fontSize: 12,
};
