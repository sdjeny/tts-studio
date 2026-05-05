import { useState, useEffect, useCallback } from "react";
import { api, Project, Character, AudioEffect, EffectRegistryItem, EffectPreset, VoiceInfo } from "../api";
import { VOICE_OPTIONS } from "../constants";

const _emptyEffect = (type: string): AudioEffect => ({
  type,
  enabled: true,
  params: {},
});
void _emptyEffect;

const EFFECT_EXAMPLES = [
  {
    icon: "👴",
    title: "用同一音色模拟不同角色",
    desc: '比如只有 "ryan" 一个男声，给"老爷爷"角色加「低沉」预设（降3半音+低通滤波），给"少年"角色加「升调+轻微回声"',
    preset: null,
  },
  {
    icon: "📻",
    title: "收音机 / 广播效果",
    desc: "电话效果 = 高低通滤波切掉极端频率 + 压缩器，让声音像从老式收音机里传出来",
    preset: "radio",
  },
  {
    icon: "🤖",
    title: "机器人 / 科幻效果",
    desc: "用「合唱/镶边」效果，极慢的 LFO 速度 + 高深度，制造机械感",
    preset: "robotic",
  },
  {
    icon: "🏔️",
    title: "山洞 / 大厅场景",
    desc: "大混响 + 轻微延迟，让角色声音像在山洞里或空旷大厅中",
    preset: "cave",
  },
  {
    icon: "📞",
    title: "电话通话效果",
    desc: "切掉 400Hz 以下和 3200Hz 以上频率，再加压缩，模拟电话听筒的窄频效果",
    preset: "telephone",
  },
];

export default function CharacterPanel({ project, onChange, onError }: {
  project: Project; onChange: () => void; onError: (m: string) => void;
}) {
  const [name, setName] = useState("");
  const [voiceId, setVoiceId] = useState("aiden");
  const [speed, setSpeed] = useState(1.0);
  const [desc, setDesc] = useState("");
  const [baseInstruct, setBaseInstruct] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [registry, setRegistry] = useState<EffectRegistryItem[]>([]);
  const [presets, setPresets] = useState<Record<string, EffectPreset>>({});
  const [voices, setVoices] = useState<Array<{ name: string; description: string }>>(VOICE_OPTIONS);

  useEffect(() => {
    api.listVoices()
      .then(v => setVoices(v.voices))
      .catch(() => {}); // fallback to VOICE_OPTIONS already set
  }, []);

  useEffect(() => {
    api.getEffectsRegistry().then(setRegistry).catch(() => {});
    api.getEffectsPresets().then(setPresets).catch(() => {});
  }, []);

  const add = async () => {
    if (!name.trim()) return;
    try {
      await api.addCharacter(project.id, { name: name.trim(), voice_id: voiceId, speed, pitch: 1.0, description: desc, base_instruct: baseInstruct, audio_effects: [] });
      setName(""); setDesc(""); setSpeed(1.0); setBaseInstruct("");
      await onChange();
    } catch (e: any) { onError(e.message); }
  };

  const remove = async (cid: string) => {
    if (!confirm("删除该角色？")) return;
    try { await api.deleteCharacter(project.id, cid); await onChange(); }
    catch (e: any) { onError(e.message); }
  };

  const saveEdit = async (cid: string, data: Partial<Character>) => {
    try {
      await api.updateCharacter(project.id, cid, data);
      setEditing(null);
      await onChange();
    } catch (e: any) { onError(e.message); }
  };

  const [applyingEffects, setApplyingEffects] = useState<string | null>(null);

  const applyEffectsToEpisode = async (cId: string) => {
    setApplyingEffects(cId);
    try {
      const res = await api.applyEffectsToEpisode(project.id, cId);
      alert(`音效应用完成：${res.applied} 条对白已处理，${res.skipped} 条跳过`);
      await onChange();
    } catch (e: any) { onError("应用音效失败: " + e.message); }
    finally { setApplyingEffects(null); }
  };

  const previewAudio = useCallback(async (effects: AudioEffect[], characterId?: string) => {
    try {
      const blob = await api.previewEffects(project.id, effects, characterId);
      const url = URL.createObjectURL(blob);
      const a = new Audio(url);
      a.play();
      a.onended = () => URL.revokeObjectURL(url);
    } catch (e: any) { onError("预览失败: " + e.message); }
  }, [project.id, onError]);

  return (
    <div>
      {/* 添加角色 */}
      <div style={{ background: "#1e293b", border: "1px solid #334155", borderRadius: 10, padding: 16, marginBottom: 16 }}>
        <h3 style={{ margin: "0 0 12px", fontSize: 15 }}>+ 添加角色</h3>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "1fr 1fr auto" }}>
          <input placeholder="角色名" value={name} onChange={(e) => setName(e.target.value)}
            style={inputStyle} />
          <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} style={inputStyle}>
            {voices.map(v => <option key={v.name} value={v.name}>{v.name} — {v.description}</option>)}
          </select>
          <button onClick={add} style={{ ...btnBlue, padding: "8px 20px" }}>添加</button>
        </div>
        <div style={{ display: "grid", gap: 10, gridTemplateColumns: "auto 1fr", marginTop: 10 }}>
          <label style={{ color: "#94a3b8", fontSize: 13, display: "flex", alignItems: "center", gap: 6 }}>
            语速: {speed.toFixed(1)}
            <input type="range" min={0.5} max={2.0} step={0.1} value={speed}
              onChange={(e) => setSpeed(parseFloat(e.target.value))} />
          </label>
          <input placeholder="描述（可选）" value={desc} onChange={(e) => setDesc(e.target.value)}
            style={inputStyle} />
        </div>
        <div style={{ marginTop: 10 }}>
          <input placeholder="基础朗读风格（可选），如：沉稳略带磁性、温和舒缓" value={baseInstruct} onChange={(e) => setBaseInstruct(e.target.value)}
            style={{ ...inputStyle, width: "100%", boxSizing: "border-box" }} />
        </div>
      </div>

      {/* 使用帮助 & 示例 */}
      <HelpSection />

      {/* 角色列表 */}
      {project.characters.length === 0 ? (
        <p style={{ color: "#64748b", textAlign: "center", padding: 30 }}>暂无角色</p>
      ) : (
        <div style={{ display: "grid", gap: 8 }}>
          {project.characters.map((ch) => (
            <div key={ch.id} style={{
              background: "#1e293b", border: "1px solid #334155",
              borderRadius: 8, padding: "12px 16px",
            }}>
              {editing === ch.id ? (
                <EditRow char={ch} registry={registry} presets={presets} voices={voices} onSave={saveEdit} onCancel={() => setEditing(null)} onPreview={previewAudio} />
              ) : (
                <div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div>
                      <span style={{ fontWeight: 600 }}>{ch.name}</span>
                      <div style={{ color: "#64748b", marginLeft: 8, fontSize: 13 }}>
                        <span>音色: {ch.voice_id} · 语速: {ch.speed}</span>
                        <span style={{ marginLeft: 8, color: "#94a3b8" }}>风格:</span>
                        <span style={{ color: ch.base_instruct ? "#f59e0b" : "#475569", marginLeft: 4 }}>
                          {ch.base_instruct || "未设置"}
                        </span>
                        {(ch.audio_effects?.length || 0) > 0 && (
                          <span style={{ color: "#a78bfa", marginLeft: 6 }}>🎛 效果×{ch.audio_effects.length}</span>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      {ch.audio_effects?.length > 0 && project.episodes?.length > 0 && (
                        <button
                          onClick={() => applyEffectsToEpisode(ch.id)}
                          style={{ ...smallBtn, color: "#a78bfa", borderColor: "#7c3aed", fontSize: 11 }}
                          disabled={applyingEffects === ch.id}
                          title="将该角色的音效应用到所有剧集的所有对白"
                        >
                          {applyingEffects === ch.id ? "⏳ 应用中..." : "✨ 应用音效到全部剧集"}
                        </button>
                      )}
                      <button onClick={() => setEditing(ch.id)} style={smallBtn}>编辑</button>
                      <button onClick={() => remove(ch.id)} style={{ ...smallBtn, color: "#ef4444", borderColor: "#ef4444" }}>删除</button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EditRow({ char, registry, presets, voices, onSave, onCancel, onPreview }: {
  char: Character;
  registry: EffectRegistryItem[];
  presets: Record<string, EffectPreset>;
  voices: Array<{ name: string; description: string }>;
  onSave: (id: string, data: Partial<Character>) => void;
  onCancel: () => void;
  onPreview: (effects: AudioEffect[], characterId?: string) => void;
}) {
  const [name, setName] = useState(char.name);
  const [voiceId, setVoiceId] = useState(char.voice_id);
  const [speed, setSpeed] = useState(char.speed);
  const [baseInstruct, setBaseInstruct] = useState(char.base_instruct || "");
  const [effects, setEffects] = useState<AudioEffect[]>(char.audio_effects || []);
  const [showEffects, setShowEffects] = useState(false);

  const updateEffect = (idx: number, patch: Partial<AudioEffect>) => {
    setEffects(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], ...patch };
      return next;
    });
  };

  const updateParam = (idx: number, key: string, value: number) => {
    setEffects(prev => {
      const next = [...prev];
      next[idx] = { ...next[idx], params: { ...next[idx].params, [key]: value } };
      return next;
    });
  };

  const addEffect = (type: string) => {
    const regItem = registry.find(r => r.type === type);
    if (!regItem) return;
    const defaults: Record<string, number> = {};
    for (const [k, v] of Object.entries(regItem.params)) {
      defaults[k] = v.default;
    }
    setEffects(prev => [...prev, { type, enabled: true, params: defaults }]);
  };

  const removeEffect = (idx: number) => {
    setEffects(prev => prev.filter((_, i) => i !== idx));
  };

  const moveEffect = (idx: number, dir: -1 | 1) => {
    const target = idx + dir;
    if (target < 0 || target >= effects.length) return;
    setEffects(prev => {
      const next = [...prev];
      [next[idx], next[target]] = [next[target], next[idx]];
      return next;
    });
  };

  const applyPreset = (key: string) => {
    const preset = presets[key];
    if (!preset) return;
    setEffects(preset.effects_chain.map(e => ({ ...e, params: { ...e.params } })));
  };

  const enabledEffects = effects.filter(e => e.enabled);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, width: "100%" }}>
      {/* 基础信息行 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <input value={name} onChange={(e) => setName(e.target.value)} style={{ ...inputStyle, flex: 1, minWidth: 100 }} />
        <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} style={inputStyle}>
          {voices.map(v => <option key={v.name} value={v.name}>{v.name} — {v.description}</option>)}
        </select>
        <label style={{ color: "#94a3b8", fontSize: 12, display: "flex", alignItems: "center", gap: 4 }}>
          语速{speed.toFixed(1)}
          <input type="range" min={0.5} max={2.0} step={0.1} value={speed}
            onChange={(e) => setSpeed(parseFloat(e.target.value))} style={{ width: 60 }} />
        </label>
        <button onClick={() => onSave(char.id, { name, voice_id: voiceId, speed, base_instruct: baseInstruct, audio_effects: effects })}
          style={{ ...btnBlue, padding: "4px 10px", fontSize: 12 }}>保存</button>
        <button onClick={onCancel} style={{ ...smallBtn, fontSize: 12 }}>取消</button>
      </div>
      {/* 基础朗读风格 */}
      <input placeholder="基础朗读风格（可选），如：沉稳略带磁性、温和舒缓" value={baseInstruct} onChange={(e) => setBaseInstruct(e.target.value)}
        style={{ ...inputStyle, width: "100%", boxSizing: "border-box" }} />

      {/* 效果链区域 */}
      <div style={{ border: "1px solid #334155", borderRadius: 8, padding: 10 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
          <button onClick={() => setShowEffects(s => !s)} style={{ ...smallBtn, fontSize: 12 }}>
            🎛 音频效果 {showEffects ? "▲" : "▼"} ({effects.length})
          </button>
          {enabledEffects.length > 0 && (
            <button onClick={() => onPreview(enabledEffects, char.id)} style={{ ...smallBtn, fontSize: 12, color: "#a78bfa", borderColor: "#7c3aed" }}>
              ▶ 预览效果
            </button>
          )}
        </div>

        {showEffects && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {/* 预设快捷应用 */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
              <span style={{ color: "#64748b", fontSize: 12 }}>预设:</span>
              {Object.entries(presets).map(([key, preset]) => (
                <button key={key} onClick={() => applyPreset(key)} style={{ ...smallBtn, fontSize: 11, color: "#a78bfa" }}>
                  {preset.name}
                </button>
              ))}
            </div>

            {/* 效果链列表 */}
            {effects.map((eff, idx) => {
              const regItem = registry.find(r => r.type === eff.type);
              return (
                <div key={idx} style={{
                  background: "#0f1117", border: "1px solid #1e293b", borderRadius: 6,
                  padding: "8px 10px", display: "flex", flexDirection: "column", gap: 6,
                  opacity: eff.enabled ? 1 : 0.5,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                    <input type="checkbox" checked={eff.enabled}
                      onChange={(e) => updateEffect(idx, { enabled: e.target.checked })} />
                    <span style={{ fontWeight: 600, fontSize: 13, color: "#e2e8f0" }}>
                      {regItem?.label || eff.type}
                    </span>
                    <span style={{ color: "#64748b", fontSize: 11 }}>{regItem?.description}</span>
                    <div style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
                      <button onClick={() => moveEffect(idx, -1)} disabled={idx === 0} style={tinyBtn}>↑</button>
                      <button onClick={() => moveEffect(idx, 1)} disabled={idx === effects.length - 1} style={tinyBtn}>↓</button>
                      <button onClick={() => removeEffect(idx)} style={{ ...tinyBtn, color: "#ef4444" }}>✕</button>
                    </div>
                  </div>
                  {regItem && (
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 6, paddingLeft: 20 }}>
                      {Object.entries(regItem.params).map(([pName, pDef]) => (
                        <label key={pName} style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "#94a3b8" }}>
                          <span style={{ minWidth: 50, color: "#64748b" }} title={pDef.description}>{pName}</span>
                          <input type="range" min={pDef.min} max={pDef.max} step={pDef.step}
                            value={eff.params[pName] ?? pDef.default}
                            onChange={(e) => updateParam(idx, pName, parseFloat(e.target.value))}
                            style={{ flex: 1, accentColor: "#7c3aed" }} />
                          <span style={{ minWidth: 32, textAlign: "right", color: "#e2e8f0", fontFamily: "monospace" }}>
                            {(eff.params[pName] ?? pDef.default).toFixed(1)}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* 添加效果 */}
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <span style={{ color: "#64748b", fontSize: 12, alignSelf: "center" }}>添加效果:</span>
              {registry.map(r => (
                <button key={r.type} onClick={() => addEffect(r.type)} style={{ ...smallBtn, fontSize: 11 }}>
                  + {r.label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function HelpSection() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ marginBottom: 16, border: "1px solid #334155", borderRadius: 10, overflow: "hidden" }}>
      <button
        onClick={() => setOpen(s => !s)}
        style={{
          width: "100%", textAlign: "left", background: "#1e293b", border: "none",
          padding: "10px 16px", color: "#e2e8f0", fontSize: 13, cursor: "pointer",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}
      >
        <span>💡 音频效果使用指南 — 一个音色如何模拟多个角色？</span>
        <span style={{ color: "#64748b" }}>{open ? "▲ 收起" : "▼ 展开"}</span>
      </button>
      {open && (
        <div style={{ padding: "12px 16px", background: "#0f172a", display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ color: "#a78bfa", fontSize: 13, fontWeight: 600, marginBottom: 4 }}>
            核心思路：用固定音色 + 后期音效 = 无限角色声线
          </div>
          <div style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.6 }}>
            TTS 音色是固定的（如 ryan、dylan），但通过对音频进行后期处理，可以让同一个音色听起来完全不同。
            每个角色可以挂载一条<strong style={{ color: "#e2e8f0" }}>效果链</strong>，在生成音频后自动处理。
          </div>
          {EFFECT_EXAMPLES.map((ex, i) => (
            <div key={i} style={{
              background: "#1e293b", border: "1px solid #334155", borderRadius: 8,
              padding: "10px 12px",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
                <span style={{ fontSize: 16 }}>{ex.icon}</span>
                <span style={{ fontWeight: 600, fontSize: 13, color: "#e2e8f0" }}>{ex.title}</span>
                {ex.preset && (
                  <span style={{
                    background: "#312e81", color: "#a78bfa", fontSize: 10,
                    padding: "1px 6px", borderRadius: 4, marginLeft: "auto",
                  }}>
                    预设: {ex.preset}
                  </span>
                )}
              </div>
              <div style={{ color: "#94a3b8", fontSize: 12, lineHeight: 1.5 }}>{ex.desc}</div>
            </div>
          ))}
          <div style={{ color: "#64748b", fontSize: 11, marginTop: 4 }}>
            💡 提示：编辑角色时点击「▶ 预览效果」可以用当前项目的音频实时试听效果。效果按从上到下的顺序叠加处理。
          </div>
        </div>
      )}
    </div>
  );
}

const inputStyle: React.CSSProperties = {
  padding: "7px 10px", background: "#0f1117", border: "1px solid #334155",
  borderRadius: 6, color: "#e2e8f0", fontSize: 13, outline: "none",
};
const btnBlue: React.CSSProperties = {
  background: "#3b82f6", color: "#fff", border: "none",
  borderRadius: 6, cursor: "pointer", fontWeight: 600,
};
const smallBtn: React.CSSProperties = {
  background: "transparent", color: "#94a3b8", border: "1px solid #334155",
  borderRadius: 4, padding: "2px 8px", cursor: "pointer", fontSize: 12,
};
const tinyBtn: React.CSSProperties = {
  background: "transparent", color: "#94a3b8", border: "1px solid #334155",
  borderRadius: 3, padding: "0px 5px", cursor: "pointer", fontSize: 11, lineHeight: "18px",
};
