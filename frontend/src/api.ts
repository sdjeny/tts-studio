const BASE = "/api";

async function request<T>(path: string, opts?: RequestInit): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (!r.ok) {
    const msg = await r.text();
    throw new Error(`${r.status}: ${msg}`);
  }
  return r.json();
}

// ── types ──────────────────────────────────────────────

export interface AudioEffect {
  type: string;
  enabled: boolean;
  params: Record<string, number>;
}

export interface EffectRegistryItem {
  type: string;
  label: string;
  description: string;
  params: Record<string, { default: number; min: number; max: number; step: number; description: string }>;
}

export interface EffectPreset {
  name: string;
  effects_chain: AudioEffect[];
}

export interface Character {
  id: string;
  name: string;
  voice_id: string;
  speed: number;
  pitch: number;
  description: string;
  base_instruct: string;
  audio_effects: AudioEffect[];
  created_at: string;
}

export interface AudioRecord {
  id: string;
  url: string;
  filename: string;
  created_at: string;
  status?: string;
  error?: string;
  raw?: boolean;
  duration?: number;
  interrupted?: boolean;
  task_id?: string;
}

export interface Dialogue {
  id: string;
  character_id: string;
  character_name: string;
  text: string;
  summary: string;
  instruct: string;
  style_enabled?: boolean;
  order: number;
  status: string;
  audio_history: AudioRecord[];
  current_audio_id: string | null;
  created_at: string;
}

export interface Episode {
  id: string;
  title: string;
  summary: string;
  dialogues: Dialogue[];
  style_enabled?: boolean;
  created_at: string;
}

/** 项目级 TTS 采样参数默认值 */
export interface TtsDefaults {
  temperature: number;       // 采样温度，越低声音越稳定，建议 0.1~1.0
  do_sample: boolean;        // true=采样 / false=贪心解码
  top_k: number;             // top-k 采样，越小越集中，建议 10~100
  top_p: number;             // 核采样阈值，越小越集中，建议 0.5~1.0
  repetition_penalty: number;// 重复惩罚，>1.0 抑制重复，建议 1.0~1.5
}

export interface Project {
  id: string;
  name: string;
  characters: Character[];
  episodes: Episode[];
  created_at: string;
  updated_at?: string;
  tts_defaults?: TtsDefaults;  // 项目级 TTS 参数（旧项目可能不存在）
}

// ── API ─────────────────────────────────────────────────

export const api = {
  // health
  health: () => request<{ status: string }>("/health"),

  // projects
  listProjects: () => request<Project[]>("/projects"),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  createProject: (name: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name }) }),
  updateProject: (id: string, name?: string, tts_defaults?: Partial<TtsDefaults>) =>
    request<Project>(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify({
        ...(name !== undefined && { name }),
        ...(tts_defaults !== undefined && { tts_defaults }),
      }),
    }),
  deleteProject: (id: string) =>
    request<void>(`/projects/${id}`, { method: "DELETE" }),

  // characters
  listCharacters: (pid: string) =>
    request<Character[]>(`/projects/${pid}/characters`),
  addCharacter: (pid: string, data: Omit<Character, "id" | "created_at">) =>
    request<Character>(`/projects/${pid}/characters`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  updateCharacter: (pid: string, cid: string, data: Partial<Character>) =>
    request<Character>(`/projects/${pid}/characters/${cid}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteCharacter: (pid: string, cid: string) =>
    request<void>(`/projects/${pid}/characters/${cid}`, { method: "DELETE" }),

  // episodes
  listEpisodes: (pid: string) =>
    request<Episode[]>(`/projects/${pid}/episodes`),
  createEpisode: (pid: string, title: string) =>
    request<Episode>(`/projects/${pid}/episodes`, {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  updateEpisode: (pid: string, eid: string, data: { title?: string; summary?: string; style_enabled?: boolean }) =>
    request<Episode>(`/projects/${pid}/episodes/${eid}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteEpisode: (pid: string, eid: string) =>
    request<void>(`/projects/${pid}/episodes/${eid}`, { method: "DELETE" }),

  // dialogues
  listDialogues: (pid: string, eid: string) =>
    request<Dialogue[]>(`/projects/${pid}/episodes/${eid}/dialogues`),
  addDialogue: (pid: string, eid: string, data: { character_id: string; text: string; instruct?: string; order?: number }) =>
    request<Dialogue>(`/projects/${pid}/episodes/${eid}/dialogues`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  batchAddDialogues: (pid: string, eid: string, items: { character_id: string; text: string }[]) =>
    request<Dialogue[]>(`/projects/${pid}/episodes/${eid}/dialogues/batch`, {
      method: "POST",
      body: JSON.stringify(items),
    }),
  updateDialogue: (pid: string, eid: string, dlgId: string, data: { character_id?: string; text?: string; instruct?: string; order?: number; style_enabled?: boolean }) =>
    request<Dialogue>(`/projects/${pid}/episodes/${eid}/dialogues/${dlgId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  deleteDialogue: (pid: string, eid: string, dlgId: string) =>
    request<void>(`/projects/${pid}/episodes/${eid}/dialogues/${dlgId}`, {
      method: "DELETE",
    }),
  purgeDialogue: (pid: string, eid: string, dlgId: string) =>
    request<{ ok: boolean; deleted_files: number }>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/purge`,
      { method: "DELETE" }
    ),
  purgeEpisodeDialogues: (pid: string, eid: string) =>
    request<{ ok: boolean; deleted_dialogues: number; deleted_files: number }>(
      `/projects/${pid}/episodes/${eid}/purge-dialogues`,
      { method: "DELETE" }
    ),

  // audio generation
  generateAudio: (pid: string, eid: string, dlgId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/generate`,
      { method: "POST" }
    ),

  // batch generate audio for all dialogues in an episode
  generateBatchAudio: (pid: string, eid: string, dialogueIds: string[]) =>
    request<{ total: number; submitted: number; failed: any[] }>(
      `/projects/${pid}/episodes/${eid}/generate-batch`,
      { method: "POST", body: JSON.stringify({ dialogue_ids: dialogueIds }) }
    ),

  // refresh dialogue (fix missing files)
  refreshDialogue: (pid: string, eid: string, dlgId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/refresh`,
      { method: "POST" }
    ),

  // batch refresh dialogues (SSE stream)
  generateBatchRefresh: (pid: string, eid: string, dialogueIds: string[]) =>
    fetch(`${BASE}/projects/${pid}/episodes/${eid}/refresh-batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dialogue_ids: dialogueIds }),
    }),

  // clear audio history
  clearAudioHistory: (pid: string, eid: string, dlgId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/history`,
      { method: "DELETE" }
    ),

  // set current audio (转正)
  setCurrentAudio: (pid: string, eid: string, dlgId: string, audioId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/history/${audioId}/activate`,
      { method: "POST" }
    ),

  // remove single audio from history
  removeAudio: (pid: string, eid: string, dlgId: string, audioId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/history/${audioId}`,
      { method: "DELETE" }
    ),

  // download
  downloadAudio: (pid: string, eid: string, dlgId: string, audioId: string) =>
    `${BASE}/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/download/${audioId}`,

  downloadEpisodeAll: (pid: string, eid: string) =>
    `${BASE}/projects/${pid}/episodes/${eid}/download-all`,

  // import / export
  exportEpisode: (pid: string, eid: string) =>
    request<Episode>(`/projects/${pid}/episodes/${eid}/export`),
  importDialogues: (pid: string, eid: string, data: { title: string; dialogues: { character_id: string; text: string; instruct?: string; order?: number }[] }) =>
    request<Dialogue[]>(`/projects/${pid}/episodes/${eid}/import`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  exportProject: (pid: string) =>
    request<Project>(`/projects/${pid}/export`),
  importProject: (pid: string, data: { name: string; characters?: any[]; episodes?: any[] }) =>
    request<{ imported: number; episode_ids: string[] }>(`/projects/${pid}/import`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  // LLM generation
  generateEpisodes: (pid: string, description: string, numEpisodes: number = 3, extra: string = "") =>
    request<{ created: number; episode_ids: string[]; story_arc: string; story_title: string }>(`/projects/${pid}/generate-episodes`, {
      method: "POST",
      body: JSON.stringify({ description, num_episodes: numEpisodes, extra }),
    }),
  generateDialogues: (pid: string, eid: string, instruction: string = "", targetDurationMin: number = 25, narrationRatio: number = 50) =>
    request<{ created: number; dialogue_ids: string[]; new_characters: string[] }>(
      `/projects/${pid}/episodes/${eid}/generate-dialogues`,
      { method: "POST", body: JSON.stringify({ instruction, target_duration_min: targetDurationMin, narration_ratio: narrationRatio }) }
    ),
  generateNextEpisode: (pid: string, eid: string) =>
    request<{ episode_id: string; title: string; summary: string }>(
      `/projects/${pid}/episodes/${eid}/generate-next`,
      { method: "POST" }
    ),
  regenerateFrom: (pid: string, eid: string, description: string, numEpisodes: number = 3, extra: string = "") =>
    request<{ created: number; episode_ids: string[]; story_arc: string; story_title: string; deleted: number }>(
      `/projects/${pid}/regenerate-from/${eid}`,
      { method: "POST", body: JSON.stringify({ description, num_episodes: numEpisodes, extra }) }
    ),
  batchReplaceCharacter: (pid: string, oldName: string, newName: string, episodeIds: string[] = []) =>
    request<{ replaced: number; affected_episodes: number; old_name: string; new_name: string }>(
      `/projects/${pid}/batch-replace-character`,
      { method: "POST", body: JSON.stringify({ old_name: oldName, new_name: newName, episode_ids: episodeIds, create_if_missing: true }) }
    ),

  // apply effects to current raw audio
  applyEffects: (pid: string, eid: string, dlgId: string) =>
    request<Dialogue>(
      `/projects/${pid}/episodes/${eid}/dialogues/${dlgId}/apply-effects`,
      { method: "POST" }
    ),

  // apply character effects to entire episode
  applyEffectsToEpisode: (pid: string, charId: string) =>
    request<{ applied: number; skipped: number }>(
      `/projects/${pid}/apply-character-effects/${charId}`,
      { method: "POST" }
    ),

  // audio effects
  getEffectsRegistry: () => request<EffectRegistryItem[]>("/audio-effects/registry"),
  getEffectsPresets: () => request<Record<string, EffectPreset>>("/audio-effects/presets"),
  previewEffects: (pid: string, effectsChain: AudioEffect[], characterId?: string) =>
    fetch(`${BASE}/projects/${pid}/audio-effects/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ effects_chain: effectsChain, character_id: characterId ?? null }),
    }).then(async r => {
      if (!r.ok) throw new Error(`${r.status}: ${await r.text()}`);
      return r.blob();
    }),

  // ── Timeline ───────────────────────────────────────────
  assembleTimeline: (pid: string, eid: string, gap: number = 0.5) =>
    request<{ timeline: any; added: number }>(
      `/projects/${pid}/episodes/${eid}/timeline/assemble`,
      { method: "POST", body: JSON.stringify({ gap }) },
    ),

  getTimeline: (pid: string, eid: string) =>
    request<{ timeline: any | null }>(`/projects/${pid}/episodes/${eid}/timeline`),

  addTimelineClip: (pid: string, eid: string, data: Record<string, any>) =>
    request<{ clip: any }>(`/projects/${pid}/episodes/${eid}/timeline/clips`, {
      method: "POST", body: JSON.stringify(data),
    }),

  updateTimelineClip: (pid: string, eid: string, clipId: string, data: Record<string, any>) =>
    request<{ clip: any }>(`/projects/${pid}/episodes/${eid}/timeline/clips/${clipId}`, {
      method: "PUT", body: JSON.stringify(data),
    }),

  deleteTimelineClip: (pid: string, eid: string, clipId: string) =>
    request<void>(`/projects/${pid}/episodes/${eid}/timeline/clips/${clipId}`, { method: "DELETE" }),

  duplicateTimelineClip: (pid: string, eid: string, clipId: string) =>
    request<{ clip: any }>(
      `/projects/${pid}/episodes/${eid}/timeline/clips/${clipId}/duplicate`,
      { method: "POST" },
    ),

  splitTimelineClip: (pid: string, eid: string, clipId: string, splitTime: number) =>
    request<{ first_clip: any; second_clip: any }>(
      `/projects/${pid}/episodes/${eid}/timeline/clips/${clipId}/split`,
      { method: "POST", body: JSON.stringify({ split_time: splitTime }) },
    ),

  addTimelineTrack: (pid: string, eid: string, name: string, type: string = "dialogue") =>
    request<{ track: any }>(`/projects/${pid}/episodes/${eid}/timeline/tracks`, {
      method: "POST", body: JSON.stringify({ name, type }) },
    ),

  updateTimelineTrack: (pid: string, eid: string, trackId: string, data: Record<string, any>) =>
    request<{ track: any }>(`/projects/${pid}/episodes/${eid}/timeline/tracks/${trackId}`, {
      method: "PUT", body: JSON.stringify(data),
    }),

  deleteTimelineTrack: (pid: string, eid: string, trackId: string) =>
    request<void>(`/projects/${pid}/episodes/${eid}/timeline/tracks/${trackId}`, { method: "DELETE" }),

  importTimelineAudio: (pid: string, eid: string, file: File) =>
    fetch(`${BASE}/projects/${pid}/episodes/${eid}/timeline/import-audio`, {
      method: "POST",
      body: (() => { const fd = new FormData(); fd.append("file", file); return fd; })(),
    }).then(r => { if (!r.ok) throw new Error(r.statusText); return r.json(); }),

  normalizeTimeline: (pid: string, eid: string, targetDb: number = -20) =>
    request<{ clips_normalized: number; clips_skipped: number }>(
      `/projects/${pid}/episodes/${eid}/timeline/normalize`,
      { method: "POST", body: JSON.stringify({ target_db: targetDb }) },
    ),

  exportTimeline: (pid: string, eid: string, data: { format?: string; sample_rate?: number; normalization_db?: number } = {}) =>
    fetch(`${BASE}/projects/${pid}/episodes/${eid}/timeline/export`, {
      method: "POST", body: JSON.stringify({ format: "wav", sample_rate: 24000, normalization_db: -20, ...data }),
    }).then(r => { if (!r.ok) throw new Error(r.statusText); return r.blob(); }),

  previewTimelineUrl: (pid: string, eid: string) =>
    `${BASE}/projects/${pid}/episodes/${eid}/timeline/preview`,

  saveTimelineSnapshot: (pid: string, eid: string) =>
    request<{ version: number; created_at: string }>(
      `/projects/${pid}/episodes/${eid}/timeline/snapshot`, { method: "POST" },
    ),

  getTimelineSnapshots: (pid: string, eid: string) =>
    request<{ snapshots: any[] }>(`/projects/${pid}/episodes/${eid}/timeline/snapshots`),

  restoreTimelineSnapshot: (pid: string, eid: string, version: number) =>
    request<{ timeline: any }>(
      `/projects/${pid}/episodes/${eid}/timeline/snapshots/${version}/restore`,
      { method: "POST" },
    ),
}

export type { Project as ProjectType };