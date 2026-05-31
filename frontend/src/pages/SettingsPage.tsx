/**
 * 系统配置页面 — 显示/编辑 config.yaml 中的所有配置节点
 *
 * - 敏感字段（api_key 等）自动脱敏显示
 * - PATCH /api/config 部分更新
 */
import { useEffect, useState, useCallback } from "react";
import { api } from "../api";

/* ── 样式常量 ─────────────────────────────────────────── */
const sectionTitle: React.CSSProperties = {
  fontSize: 15,
  fontWeight: 700,
  color: "#e2e8f0",
  marginBottom: 12,
  display: "flex",
  alignItems: "center",
  gap: 8,
};

const labelStyle: React.CSSProperties = {
  fontSize: 12,
  color: "#94a3b8",
  marginBottom: 4,
  display: "block",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  background: "#1e293b",
  border: "1px solid #334155",
  borderRadius: 6,
  color: "#e2e8f0",
  fontSize: 13,
  outline: "none",
};

const inputNumberStyle: React.CSSProperties = {
  ...inputStyle,
  width: 140,
};

const btnPrimary: React.CSSProperties = {
  padding: "10px 28px",
  background: "#3b82f6",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
  fontWeight: 600,
  fontSize: 14,
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

/* ── 敏感字段关键词 ──────────────────────────────────── */
const SENSITIVE_KEYS = new Set([
  "api_key",
  "secret_key",
  "token",
  "password",
  "secret",
  "access_key",
  "access_token",
  "private_key",
]);

function isSensitiveField(key: string): boolean {
  const lower = key.toLowerCase();
  for (const sk of SENSITIVE_KEYS) {
    if (lower.includes(sk)) return true;
  }
  return false;
}

/* ── Section 图标映射 ────────────────────────────────── */
const SECTION_ICONS: Record<string, string> = {
  llm: "🤖",
  tts: "🔊",
  vector: "📐",
  embedding: "📐",
  audio: "🎵",
  server: "🖥️",
  database: "🗄️",
  storage: "💾",
  log: "📝",
  model: "🧠",
  stt: "🎤",
  whisper: "🎤",
};

function getSectionIcon(key: string): string {
  const lower = key.toLowerCase();
  for (const [kw, icon] of Object.entries(SECTION_ICONS)) {
    if (lower.includes(kw)) return icon;
  }
  return "⚙️";
}

/* ── 展示名映射（中英文） ────────────────────────────── */
const SECTION_LABELS: Record<string, string> = {
  llm: "LLM 大语言模型",
  tts: "TTS 语音合成",
  vector: "向量数据库",
  embedding: "Embedding 模型",
  audio: "音频配置",
  server: "服务器",
  database: "数据库",
  storage: "存储",
  stt: "STT 语音识别",
  whisper: "Whisper 语音识别",
  model: "模型",
};

function getSectionLabel(key: string): string {
  return SECTION_LABELS[key.toLowerCase()] || key;
}

/* ── 字段描述（常见字段提供 tooltip 提示） ───────────── */
const FIELD_HINTS: Record<string, string> = {
  base_url: "API 地址，如 https://api.openai.com/v1",
  api_key: "API 密钥，保存时如果为脱敏值则自动跳过",
  model: "模型名称",
  timeout: "请求超时时间（秒）",
  max_tokens: "最大 token 数",
  temperature: "生成温度，越高越随机（0.0~2.0）",
  top_p: "核采样阈值",
  top_k: "Top-K 采样",
  url: "服务地址",
  host: "监听地址",
  port: "监听端口",
  path: "文件路径",
  model_path: "模型文件路径",
  sample_rate: "采样率（Hz）",
  chunk_size: "分块大小", /* #105 */
  num_episodes: "生成剧集数", /* #105 */
  target_duration_min: "目标时长（分钟）", /* #105 */
  narration_ratio: "旁白占比（%）", /* #105 */
  do_sample: "是否启用采样", /* #105 */
  repetition_penalty: "重复惩罚系数（>1 降低重复）", /* #105 */
  voice_id: "默认语音 ID", /* #105 */
};

function getFieldHint(key: string): string {
  return FIELD_HINTS[key] || "";
}

/* ── 值类型判断 ──────────────────────────────────────── */
function isNumericString(v: string): boolean {
  return /^-?\d+(\.\d+)?$/.test(v.trim());
}

/* ── 组件 ─────────────────────────────────────────────── */

export default function SettingsPage() {
  const [config, setConfig] = useState<Record<string, any> | null>(null);
  const [edited, setEdited] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [toast, setToast] = useState<{ type: "ok" | "err"; msg: string } | null>(null);

  /* 加载配置 */
  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getConfig();
      setConfig(data);
      setEdited(JSON.parse(JSON.stringify(data)));
      setDirty(false);
    } catch (e: any) {
      showToast("err", `加载配置失败: ${e.message}`);
    }
    setLoading(false);
  }, []);

  useEffect(() => { load(); }, [load]);

  /* toast 提示 */
  const showToast = (type: "ok" | "err", msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  /* 更新某个 section 下的某个字段 */
  const updateField = (section: string, key: string, value: any) => {
    setEdited((prev) => {
      const next = { ...prev };
      next[section] = { ...next[section], [key]: value };
      return next;
    });
    setDirty(true);
  }; /* #105 */

  /* #105: 更新嵌套对象（如 defaults.temperature）的子字段 */
  const updateNestedField = (
    section: string,
    parentKey: string,
    subKey: string,
    subVal: any
  ) => { /* #105 */
    setEdited((prev) => { /* #105 */
      const next = { ...prev }; /* #105 */
      const nested = { ...(next[section]?.[parentKey] || {}) }; /* #105 */
      nested[subKey] = subVal; /* #105 */
      next[section] = { ...next[section], [parentKey]: nested }; /* #105 */
      return next; /* #105 */
    }); /* #105 */
    setDirty(true); /* #105 */
  }; /* #105 */

  /* 保存 */
  const handleSave = async () => {
    if (!config || !edited) return;
    setSaving(true);

    // 计算 diff：只发送有变化的 section
    const diff: Record<string, any> = {};
    for (const sectionKey of Object.keys(edited)) {
      const origSection = config[sectionKey] || {};
      const editSection = edited[sectionKey] || {};
      const sectionDiff: Record<string, any> = {};
      let hasChange = false;

      for (const fieldKey of Object.keys(editSection)) {
        const origVal = origSection[fieldKey];
        const editVal = editSection[fieldKey];

        // 如果是敏感字段且值未变化，跳过（脱敏后相等表示未修改）
        if (isSensitiveField(fieldKey) && typeof editVal === "string" && typeof origVal === "string") {
          if (editVal === origVal) continue;
        }

        if (JSON.stringify(origVal) !== JSON.stringify(editVal)) {
          sectionDiff[fieldKey] = editVal;
          hasChange = true;
        }
      }
      if (hasChange) {
        diff[sectionKey] = sectionDiff;
      }
    }

    if (Object.keys(diff).length === 0) {
      showToast("ok", "没有需要保存的修改");
      setSaving(false);
      return;
    }

    try {
      const result = await api.updateConfig(diff);
      setConfig(result);
      setEdited(JSON.parse(JSON.stringify(result)));
      setDirty(false);
      showToast("ok", "✅ 配置已保存");
    } catch (e: any) {
      showToast("err", `保存失败: ${e.message}`);
    }
    setSaving(false);
  };

  /* 重置修改 */
  const handleReset = () => {
    if (config) {
      setEdited(JSON.parse(JSON.stringify(config)));
      setDirty(false);
    }
  };

  /* 渲染单个字段 */
  const renderField = (section: string, key: string, value: any) => {
    const sensitive = isSensitiveField(key);
    const hint = getFieldHint(key);
    const fieldType = typeof value;

    return (
      <div key={key} style={{ marginBottom: 12 }}>
        <label style={labelStyle}>
          {key}
          {sensitive && (
            <span style={{
              marginLeft: 6, fontSize: 10, color: "#f59e0b",
              background: "#78350f22", borderRadius: 3, padding: "1px 5px",
            }}>
              🔒 敏感
            </span>
          )}
          {hint && (
            <span style={{ marginLeft: 6, fontSize: 10, color: "#475569" }}>
              {hint}
            </span>
          )}
        </label>

        {fieldType === "object" && value !== null && !Array.isArray(value) ? ( /* #105 */
          <div key={key} style={{ marginBottom: 12 }}>
            <label style={{ ...labelStyle, fontSize: 11, color: "#64748b", marginBottom: 6 }}>
              {key}
              {hint && (
                <span style={{ marginLeft: 6, fontSize: 10, color: "#475569" }}>
                  {hint}
                </span>
              )}
            </label>
            {Object.entries(value).length === 0 ? ( /* #105 */
              <div style={{ fontSize: 11, fontStyle: "italic", color: "#64748b", paddingLeft: 12 }}>
                无配置项
              </div>
            ) : (
              <div style={{ /* #105 */
                paddingLeft: 12,
                borderLeft: "2px solid #334155",
                marginTop: 8,
                marginBottom: 12,
                display: "grid",
                gap: "4px 0",
              }}>
                {(Object.entries(value) as [string, any][]).map(([subKey, subVal]) => { /* #105 */
                  const subSensitive = isSensitiveField(subKey);
                  const subHint = getFieldHint(subKey);
                  const subType = typeof subVal;
                  return (
                    <div key={subKey} style={{ marginBottom: 8 }}>
                      <label style={labelStyle}>
                        {subKey}
                        {subSensitive && (
                          <span style={{
                            marginLeft: 6, fontSize: 10, color: "#f59e0b",
                            background: "#78350f22", borderRadius: 3, padding: "1px 5px",
                          }}>
                            🔒 敏感
                          </span>
                        )}
                        {subHint && (
                          <span style={{ marginLeft: 6, fontSize: 10, color: "#475569" }}>
                            {subHint}
                          </span>
                        )}
                      </label>
                      {subType === "boolean" ? ( /* #105 */
                        <div style={{ display: "flex", gap: 8 }}>
                          <button
                            onClick={() => updateNestedField(section, key, subKey, true)}
                            style={{
                              flex: 1, padding: "6px 0",
                              background: subVal ? "#3b82f6" : "#1e293b",
                              color: subVal ? "#fff" : "#64748b",
                              border: `1px solid ${subVal ? "#3b82f6" : "#334155"}`,
                              borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                            }}
                          >
                            True
                          </button>
                          <button
                            onClick={() => updateNestedField(section, key, subKey, false)}
                            style={{
                              flex: 1, padding: "6px 0",
                              background: !subVal ? "#3b82f6" : "#1e293b",
                              color: !subVal ? "#fff" : "#64748b",
                              border: `1px solid ${!subVal ? "#3b82f6" : "#334155"}`,
                              borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
                            }}
                          >
                            False
                          </button>
                        </div>
                      ) : subType === "number" ? ( /* #105 */
                        <input
                          type="number"
                          value={String(subVal)}
                          onChange={(e) => {
                            const raw = e.target.value;
                            const num = Number(raw);
                            if (!isNaN(num) && raw !== "") {
                              updateNestedField(section, key, subKey, Number.isInteger(subVal) ? parseInt(raw, 10) : num);
                            } else if (raw === "") {
                              updateNestedField(section, key, subKey, 0);
                            }
                          }}
                          style={inputNumberStyle}
                        />
                      ) : ( /* #105 string fallback */
                        <input
                          type={subSensitive ? "password" : "text"}
                          value={String(subVal ?? "")}
                          onChange={(e) => {
                            const val = e.target.value;
                            if (typeof subVal === "number" || (typeof subVal === "string" && isNumericString(subVal))) {
                              const num = Number(val);
                              if (!isNaN(num) && val.trim() !== "") {
                                updateNestedField(section, key, subKey, typeof subVal === "number" ? num : val);
                                return;
                              }
                            }
                            updateNestedField(section, key, subKey, val);
                          }}
                          style={{
                            ...inputStyle,
                            ...(subSensitive ? { fontFamily: "monospace", letterSpacing: 2 } : {}),
                          }}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : fieldType === "boolean" ? (
          <div style={{ display: "flex", gap: 8 }}>
            <button
              onClick={() => updateField(section, key, true)}
              style={{
                flex: 1, padding: "6px 0",
                background: value ? "#3b82f6" : "#1e293b",
                color: value ? "#fff" : "#64748b",
                border: `1px solid ${value ? "#3b82f6" : "#334155"}`,
                borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
              }}
            >
              True
            </button>
            <button
              onClick={() => updateField(section, key, false)}
              style={{
                flex: 1, padding: "6px 0",
                background: !value ? "#3b82f6" : "#1e293b",
                color: !value ? "#fff" : "#64748b",
                border: `1px solid ${!value ? "#3b82f6" : "#334155"}`,
                borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 600,
              }}
            >
              False
            </button>
          </div>
        ) : fieldType === "number" ? (
          <input
            type="number"
            value={String(value)}
            onChange={(e) => {
              const raw = e.target.value;
              const num = Number(raw);
              if (!isNaN(num) && raw !== "") {
                updateField(section, key, Number.isInteger(value) ? parseInt(raw, 10) : num);
              } else if (raw === "") {
                updateField(section, key, 0);
              }
            }}
            style={inputNumberStyle}
          />
        ) : (
          <input
            type={sensitive ? "password" : "text"}
            value={String(value ?? "")}
            onChange={(e) => {
              const val = e.target.value;
              // 如果原始值是数字字符串，尝试保持
              if (typeof value === "number" || (typeof value === "string" && isNumericString(value))) {
                const num = Number(val);
                if (!isNaN(num) && val.trim() !== "") {
                  updateField(section, key, typeof value === "number" ? num : val);
                  return;
                }
              }
              updateField(section, key, val);
            }}
            style={{
              ...inputStyle,
              ...(sensitive ? { fontFamily: "monospace", letterSpacing: 2 } : {}),
            }}
          />
        )}
      </div>
    );
  };

  /* ── render ─────────────────────────────────────────── */
  if (loading) return <p style={{ color: "#64748b" }}>加载配置中...</p>;

  if (!config) {
    return (
      <div style={{ color: "#ef4444", padding: 20 }}>
        无法加载配置，请检查后端是否正常运行。
      </div>
    );
  }

  const sections = Object.entries(edited || config).filter(
    ([_, v]) => v && typeof v === "object" && !Array.isArray(v)
  );

  return (
    <div style={{ maxWidth: 800, margin: "0 auto" }}>
      {/* 说明卡片 */}
      <div style={{
        background: "linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%)",
        border: "1px solid #312e81",
        borderRadius: 8,
        padding: "14px 16px",
        marginBottom: 20,
      }}>
        <div style={{ fontSize: 14, color: "#818cf8", fontWeight: 600, marginBottom: 4 }}>
          ⚙️ 系统配置
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.7 }}>
          以下配置对应 <code style={{ color: "#c7d2fe", background: "#1e293b", padding: "1px 4px", borderRadius: 3 }}>config.yaml</code> 中的各配置节点。
          <br />
          敏感字段（<span style={{ color: "#f59e0b" }}>api_key</span> 等）显示为脱敏值，保存时如果未修改则自动跳过。
        </div>
      </div>

      {/* 配置区段 */}
      <div style={{ display: "grid", gap: 16 }}>
        {sections.map(([sectionKey, sectionVal]) => {
          const fields = Object.entries(sectionVal as Record<string, any>);
          return (
            <div key={sectionKey} style={{
              background: "#0f1117",
              border: "1px solid #1e293b",
              borderRadius: 10,
              padding: "18px 20px",
            }}>
              <div style={sectionTitle}>
                <span style={{ fontSize: 20 }}>{getSectionIcon(sectionKey)}</span>
                <span>{getSectionLabel(sectionKey)}</span>
                <span style={{
                  marginLeft: "auto", fontSize: 11, color: "#475569",
                  fontFamily: "monospace", background: "#1e293b",
                  padding: "2px 8px", borderRadius: 4,
                }}>
                  {sectionKey}
                </span>
              </div>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: "4px 20px",
              }}>
                {fields.map(([fieldKey, fieldVal]) =>
                  renderField(sectionKey, fieldKey, fieldVal)
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* 无配置节点提示 */}
      {sections.length === 0 && (
        <div style={{
          textAlign: "center", padding: 40, color: "#64748b",
          background: "#0f1117", borderRadius: 8, border: "1px solid #1e293b",
        }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>📭</div>
          <div>配置文件为空，请先在 <code style={{ color: "#c7d2fe" }}>config.yaml</code> 中添加配置项</div>
        </div>
      )}

      {/* 底部操作栏 */}
      <div style={{
        position: "sticky",
        bottom: 0,
        marginTop: 20,
        padding: "16px 0",
        display: "flex",
        gap: 12,
        alignItems: "center",
        borderTop: "1px solid #1e293b",
        background: "#0f1117",
      }}>
        <button
          onClick={handleSave}
          disabled={saving || !dirty}
          style={{
            ...btnPrimary,
            ...(dirty ? {} : { background: "#334155", color: "#64748b", cursor: "default" }),
          }}
        >
          {saving ? "⏳ 保存中..." : dirty ? "💾 保存配置" : "✓ 已保存"}
        </button>
        {dirty && (
          <button onClick={handleReset} style={btnGhost}>
            放弃修改
          </button>
        )}
        <button onClick={load} style={btnGhost}>
          🔄 刷新
        </button>
      </div>

      {/* Toast */}
      {toast && (
        <div style={{
          position: "fixed",
          top: 20,
          right: 20,
          padding: "12px 20px",
          borderRadius: 8,
          fontSize: 14,
          fontWeight: 600,
          color: "#fff",
          background: toast.type === "ok" ? "#22c55e" : "#ef4444",
          boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
          zIndex: 9999,
          animation: "fadeIn 0.3s ease",
        }}>
          {toast.msg}
        </div>
      )}
    </div>
  );
}
