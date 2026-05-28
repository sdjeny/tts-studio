/**
 * 项目设置面板 —— TTS 采样参数默认值配置
 *
 * 这些参数作为项目级默认值，在对白生成音频时使用。
 * 保守默认值旨在最小化不同句子间的声音波动，让同一角色的不同台词听起来更一致。
 *
 * 参数说明：
 * - temperature（温度）：控制采样的随机性。越低越确定、越稳定；越高越随机、变化越大。
 * - do_sample：是否使用采样。true=采样（更自然），false=贪心解码（最稳定但可能生硬）。
 * - top_k：只从概率最高的 k 个 token 中采样。越小输出越集中、越可预测。
 * - top_p（核采样）：从累积概率达到 p 的 token 中采样。越小采样池越窄。
 * - repetition_penalty（重复惩罚）：>1.0 时抑制重复模式，值越大抑制越强。
 */
import { useState, useEffect } from "react";
import { api, Project, TtsDefaults, GenDefaults } from "../api";
import { VOICE_OPTIONS } from "../constants";

// 各参数的取值范围和步长（voice_id 是字符串，单独处理）
const RANGES: Record<keyof Omit<TtsDefaults, "voice_id">, { min: number; max: number; step: number; label: string; desc: string }> = {
  temperature: {
    min: 0.05, max: 1.5, step: 0.05, label: "温度 (temperature)",
    desc: "越低越稳定。0.1~0.3 声音一致性最好，0.7+ 变化较大。",
  },
  do_sample: {
    min: 0, max: 1, step: 1, label: "采样模式 (do_sample)",
    desc: "开=采样（自然），关=贪心解码（最稳定但可能生硬）。",
  },
  top_k: {
    min: 5, max: 100, step: 5, label: "Top-K",
    desc: "越小采样池越窄，输出越集中。10~30 推荐。",
  },
  top_p: {
    min: 0.3, max: 1.0, step: 0.05, label: "Top-P（核采样）",
    desc: "越小越集中。0.7~0.9 推荐，1.0=不截断。",
  },
  repetition_penalty: {
    min: 1.0, max: 2.0, step: 0.05, label: "重复惩罚",
    desc: ">1.0 抑制重复模式。1.05~1.2 推荐，过大可能影响流畅度。",
  },
};

// 保守默认值（与服务端保持一致）
const CONSERVATIVE_DEFAULTS: TtsDefaults = {
  temperature: 0.05,
  do_sample: false,
  top_k: 5,
  top_p: 0.3,
  repetition_penalty: 1.1,
  voice_id: "aiden",
};

// 官方默认值（对比用）
const OFFICIAL_DEFAULTS: TtsDefaults = {
  temperature: 0.9,
  do_sample: true,
  top_k: 50,
  top_p: 1.0,
  repetition_penalty: 1.05,
  voice_id: "aiden",
};

// 生成参数全局默认值
const GEN_GLOBAL_DEFAULTS: GenDefaults = {
  num_episodes: 3,
  target_duration_min: 25,
  narration_ratio: 50,
};

interface Props {
  project: Project;
  onChange: () => void;
  onError: (msg: string) => void;
}

export default function ProjectSettings({ project, onChange, onError }: Props) {
  // 从项目数据初始化，旧项目可能没有 tts_defaults
  const [values, setValues] = useState<TtsDefaults>(() => ({
    ...CONSERVATIVE_DEFAULTS,
    ...project.tts_defaults,
  }));
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [globalDefaults, setGlobalDefaults] = useState<TtsDefaults>(CONSERVATIVE_DEFAULTS);
  const [voices, setVoices] = useState<Array<{ name: string; description: string }>>(VOICE_OPTIONS);
  // gen_defaults 状态
  const [genValues, setGenValues] = useState<GenDefaults>(() => ({
    ...GEN_GLOBAL_DEFAULTS,
    ...project.gen_defaults,
  }));
  const [genDirty, setGenDirty] = useState(false);

  // 项目切换时重置
  useEffect(() => {
    setValues({ ...CONSERVATIVE_DEFAULTS, ...project.tts_defaults });
    setDirty(false);
    setGenValues({ ...GEN_GLOBAL_DEFAULTS, ...project.gen_defaults });
    setGenDirty(false);
  }, [project.id, project.tts_defaults, project.gen_defaults]);

  // 从 API 加载全局默认值
  useEffect(() => {
    api.getGlobalDefaults()
      .then(setGlobalDefaults)
      .catch(() => {}); // 失败时使用硬编码 fallback
  }, []);

  // 从 API 动态加载音色列表
  const loadVoices = () => {
    api.listVoices()
      .then(v => setVoices(v.voices))
      .catch(() => {}); // fallback to VOICE_OPTIONS
  };

  useEffect(() => {
    loadVoices();
  }, []);

  const updateField = (field: keyof TtsDefaults, val: number | boolean | string) => {
    setValues((prev) => ({ ...prev, [field]: val }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await api.updateProject(project.id, undefined, values);
      onChange();
      setDirty(false);
      onError("✅ TTS 参数已保存");
    } catch (e: any) {
      onError(`保存失败: ${e.message}`);
    }
    setSaving(false);
  };

  const handleResetToGlobal = () => {
    setValues({ ...globalDefaults });
    setDirty(true);
  };

  const handleResetOfficial = () => {
    setValues({ ...OFFICIAL_DEFAULTS });
    setDirty(true);
  };

  const updateGenField = (field: keyof GenDefaults, val: number) => {
    setGenValues((prev) => ({ ...prev, [field]: val }));
    setGenDirty(true);
  };

  const handleGenSave = async () => {
    setSaving(true);
    try {
      await api.updateProject(project.id, undefined, undefined, genValues);
      onChange();
      setGenDirty(false);
      onError("✅ 生成参数已保存");
    } catch (e: any) {
      onError(`保存失败: ${e.message}`);
    }
    setSaving(false);
  };

  const handleGenResetToGlobal = () => {
    setGenValues({ ...GEN_GLOBAL_DEFAULTS });
    setGenDirty(true);
  };

  const sliderStyle: React.CSSProperties = {
    width: "100%",
    accentColor: "#3b82f6",
  };

  const labelStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  };

  return (
    <div style={{ display: "grid", gap: 20, maxWidth: 640 }}>
      {/* 说明卡片 */}
      <div style={{
        background: "linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%)",
        border: "1px solid #312e81",
        borderRadius: 8,
        padding: "14px 16px",
      }}>
        <div style={{ fontSize: 14, color: "#818cf8", fontWeight: 600, marginBottom: 6 }}>
          🎛️ TTS 采样参数默认值
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7 }}>
          以下参数作为本项目所有对白生成音频时的默认值。
          <br />
          <strong style={{ color: "#c7d2fe" }}>保守默认值</strong>（当前推荐）可使不同句子间的声音更一致。
          如需更多变化/创意，可调整为<strong style={{ color: "#fbbf24" }}>官方默认值</strong>。
        </div>
      </div>

      {/* 快捷预设 */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b", alignSelf: "center", marginRight: 4 }}>快捷预设：</span>
        <button onClick={handleResetToGlobal} style={btnPreset}>
          🔄 恢复全局默认
        </button>
        <button onClick={handleResetOfficial} style={btnPreset}>
          🔬 官方默认（变化较大）
        </button>
      </div>

      {/* 音色选择（字符串类型，单独处理） */}
      <div style={{
        background: "#0f1117",
        border: "1px solid #1e293b",
        borderRadius: 8,
        padding: "12px 14px",
      }}>
        <div style={labelStyle}>
          <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
            默认音色 (voice_id)
          </label>
          <span style={{
            fontSize: 14,
            color: "#3b82f6",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            minWidth: 48,
            textAlign: "right",
          }}>
            {values.voice_id}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
          项目级默认音色，对白生成时未指定音色则使用此值。
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <select
            value={values.voice_id}
            onChange={(e) => updateField("voice_id", e.target.value)}
            style={{
              flex: 1, padding: "8px 10px",
              background: "#1e293b", color: "#e2e8f0",
              border: "1px solid #334155", borderRadius: 6,
              fontSize: 13, cursor: "pointer",
            }}
          >
            {voices.map((v) => (
              <option key={v.name} value={v.name}>{v.name} - {v.description}</option>
            ))}
          </select>
          <button
            onClick={loadVoices}
            title="刷新音色列表"
            style={{
              background: "#1e293b", color: "#94a3b8",
              border: "1px solid #334155", borderRadius: 6,
              padding: "8px 10px", cursor: "pointer",
              fontSize: 14, lineHeight: 1,
            }}
          >
            🔄
          </button>
        </div>
      </div>

      {/* 各参数滑块 */}
      {(Object.keys(RANGES) as (keyof typeof RANGES)[]).map((field) => {
        const cfg = RANGES[field];
        const val = values[field];
        const isBoolean = field === "do_sample";

        return (
          <div key={field} style={{
            background: "#0f1117",
            border: "1px solid #1e293b",
            borderRadius: 8,
            padding: "12px 14px",
          }}>
            <div style={labelStyle}>
              <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
                {cfg.label}
              </label>
              <span style={{
                fontSize: 14,
                color: "#3b82f6",
                fontWeight: 700,
                fontVariantNumeric: "tabular-nums",
                minWidth: 48,
                textAlign: "right",
              }}>
                {isBoolean ? (val ? "采样" : "贪心") : String(val)}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>{cfg.desc}</div>

            {isBoolean ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  onClick={() => updateField("do_sample", true)}
                  style={{
                    flex: 1, padding: "6px 0",
                    background: val ? "#3b82f6" : "#1e293b",
                    color: val ? "#fff" : "#64748b",
                    border: `1px solid ${val ? "#3b82f6" : "#334155"}`,
                    borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                  }}
                >
                  采样（自然）
                </button>
                <button
                  onClick={() => updateField("do_sample", false)}
                  style={{
                    flex: 1, padding: "6px 0",
                    background: !val ? "#3b82f6" : "#1e293b",
                    color: !val ? "#fff" : "#64748b",
                    border: `1px solid ${!val ? "#3b82f6" : "#334155"}`,
                    borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                  }}
                >
                  贪心（最稳定）
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                <span style={{ fontSize: 10, color: "#475569" }}>{cfg.min}</span>
                <input
                  type="range"
                  min={cfg.min}
                  max={cfg.max}
                  step={cfg.step}
                  value={val as number}
                  onChange={(e) => updateField(field, parseFloat(e.target.value))}
                  style={sliderStyle}
                />
                <span style={{ fontSize: 10, color: "#475569" }}>{cfg.max}</span>
              </div>
            )}

            {/* 标记当前值偏离保守默认的程度 */}
            {field !== "do_sample" && (val as number) !== CONSERVATIVE_DEFAULTS[field] && (
              <div style={{ fontSize: 10, color: "#475569", marginTop: 4 }}>
                ℹ 保守默认: {CONSERVATIVE_DEFAULTS[field]} / 官方默认: {OFFICIAL_DEFAULTS[field]}
              </div>
            )}
          </div>
        );
      })}

      {/* TTS 保存按钮 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          style={{
            padding: "10px 28px",
            background: dirty ? "#3b82f6" : "#334155",
            color: dirty ? "#fff" : "#64748b",
            border: "none",
            borderRadius: 8,
            cursor: saving ? "wait" : dirty ? "pointer" : "default",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          {saving ? "⏳ 保存中..." : dirty ? "💾 保存设置" : "✓ 已保存"}
        </button>
        {dirty && (
          <button
            onClick={() => { setValues({ ...CONSERVATIVE_DEFAULTS, ...project.tts_defaults }); setDirty(false); }}
            style={{ ...btnGhost }}
          >
            放弃修改
          </button>
        )}
      </div>

      {/* 风格开关默认值 */}
      <div style={{
        background: "#0f1117",
        border: "1px solid #1e293b",
        borderRadius: 8,
        padding: "12px 14px",
      }}>
        <div style={labelStyle}>
          <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
            🎭 新建剧集/对白默认风格开关
          </label>
          <button
            onClick={async () => {
              const newVal = !project.default_style_enabled;
              try {
                await api.updateProject(project.id, undefined, undefined, undefined, undefined, newVal);
                onChange();
              } catch (e: any) {
                onError(`保存失败: ${e.message}`);
              }
            }}
            style={{
              fontSize: 12,
              padding: "3px 10px",
              borderRadius: 4,
              border: "1px solid",
              borderColor: project.default_style_enabled ? "#f59e0b" : "#334155",
              background: project.default_style_enabled ? "#f59e0b22" : "transparent",
              color: project.default_style_enabled ? "#f59e0b" : "#64748b",
              cursor: "pointer",
              fontWeight: 600,
            }}
          >
            🎭 风格{project.default_style_enabled ? "开" : "关"}
          </button>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginTop: 4 }}>
          控制新建剧集和对白时 style_enabled 的默认值。开启后，新剧集和新对白默认启用风格模式（角色风格+场景情绪）。
        </div>
      </div>

      {/* 生成参数默认值 */}

      {/* divider */}
      <div style={{ height: 1, background: "#1e293b", margin: "12px 0" }} />

      <div style={{
        background: "linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%)",
        border: "1px solid #312e81",
        borderRadius: 8,
        padding: "14px 16px",
      }}>
        <div style={{ fontSize: 14, color: "#818cf8", fontWeight: 600, marginBottom: 6 }}>
          🎬 生成参数默认值
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7 }}>
          以下参数作为本项目生成大纲和对白时的默认值。可在 AI 生成面板中临时调整。
        </div>
      </div>

      {/* 快捷预设 */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <span style={{ fontSize: 12, color: "#64748b", alignSelf: "center", marginRight: 4 }}>快捷预设：</span>
        <button onClick={handleGenResetToGlobal} style={btnPreset}>
          🔄 恢复全局默认
        </button>
      </div>

      {/* 默认集数 */}
      <div style={{
        background: "#0f1117",
        border: "1px solid #1e293b",
        borderRadius: 8,
        padding: "12px 14px",
      }}>
        <div style={labelStyle}>
          <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
            默认集数
          </label>
          <span style={{
            fontSize: 14,
            color: "#3b82f6",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            minWidth: 48,
            textAlign: "right",
          }}>
            {genValues.num_episodes}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
          生成大纲时的默认集数。
        </div>
        <input
          type="number"
          min={1}
          max={99}
          step={1}
          value={genValues.num_episodes}
          onChange={(e) => updateGenField("num_episodes", Math.max(1, Math.min(99, parseInt(e.target.value) || 3)))}
          style={{
            width: 80,
            padding: "8px 10px",
            background: "#1e293b",
            color: "#e2e8f0",
            border: "1px solid #334155",
            borderRadius: 6,
            fontSize: 13,
            outline: "none",
          }}
        />
      </div>

      {/* 每集时长(min) */}
      <div style={{
        background: "#0f1117",
        border: "1px solid #1e293b",
        borderRadius: 8,
        padding: "12px 14px",
      }}>
        <div style={labelStyle}>
          <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
            每集时长 (min)
          </label>
          <span style={{
            fontSize: 14,
            color: "#3b82f6",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            minWidth: 48,
            textAlign: "right",
          }}>
            {genValues.target_duration_min}
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
          每集对白生成的目标时长。
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#475569" }}>1</span>
          <input
            type="range"
            min={1}
            max={120}
            step={5}
            value={genValues.target_duration_min}
            onChange={(e) => updateGenField("target_duration_min", parseInt(e.target.value))}
            style={sliderStyle}
          />
          <span style={{ fontSize: 10, color: "#475569" }}>120</span>
        </div>
      </div>

      {/* 旁白比例 */}
      <div style={{
        background: "#0f1117",
        border: "1px solid #1e293b",
        borderRadius: 8,
        padding: "12px 14px",
      }}>
        <div style={labelStyle}>
          <label style={{ fontSize: 13, color: "#e2e8f0", fontWeight: 600 }}>
            旁白比例 (%)
          </label>
          <span style={{
            fontSize: 14,
            color: "#3b82f6",
            fontWeight: 700,
            fontVariantNumeric: "tabular-nums",
            minWidth: 48,
            textAlign: "right",
          }}>
            {genValues.narration_ratio}%
          </span>
        </div>
        <div style={{ fontSize: 11, color: "#64748b", marginBottom: 8 }}>
          旁白占比，剩余为对白。0%=纯对白，100%=纯旁白。
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <span style={{ fontSize: 10, color: "#475569" }}>0%</span>
          <input
            type="range"
            min={0}
            max={100}
            step={10}
            value={genValues.narration_ratio}
            onChange={(e) => updateGenField("narration_ratio", parseInt(e.target.value))}
            style={sliderStyle}
          />
          <span style={{ fontSize: 10, color: "#475569" }}>100%</span>
        </div>
      </div>

      {/* 保存按钮 */}
      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
        <button
          onClick={handleGenSave}
          disabled={saving || !genDirty}
          style={{
            padding: "10px 28px",
            background: genDirty ? "#3b82f6" : "#334155",
            color: genDirty ? "#fff" : "#64748b",
            border: "none",
            borderRadius: 8,
            cursor: saving ? "wait" : genDirty ? "pointer" : "default",
            fontWeight: 600,
            fontSize: 14,
          }}
        >
          {saving ? "⏳ 保存中..." : genDirty ? "💾 保存设置" : "✓ 已保存"}
        </button>
        {genDirty && (
          <button
            onClick={() => { setGenValues({ ...GEN_GLOBAL_DEFAULTS, ...project.gen_defaults }); setGenDirty(false); }}
            style={{ ...btnGhost }}
          >
            放弃修改
          </button>
        )}
      </div>
    </div>
  );
}

const btnPreset: React.CSSProperties = {
  background: "#1e293b",
  color: "#94a3b8",
  border: "1px solid #334155",
  borderRadius: 6,
  padding: "4px 12px",
  cursor: "pointer",
  fontSize: 12,
};

const btnGhost: React.CSSProperties = {
  background: "transparent",
  color: "#94a3b8",
  border: "1px solid #334155",
  borderRadius: 6,
  padding: "4px 12px",
  cursor: "pointer",
  fontSize: 13,
};
