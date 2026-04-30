/** Timeline type definitions for TTS Studio multi-track audio editor. */

export interface TimelineClip {
  id: string;
  track_id: string;
  source_type: "dialogue" | "imported";
  source_id: string;
  source_audio_id?: string;
  audio_filename: string;
  offset_in_source: number;
  duration_in_source: number;
  start_time: number;
  duration: number;
  volume: number;
  fadeIn: number;
  fadeOut: number;
  crossfade_in: number;
  crossfade_out: number;
  effects_chain: any[];
}

export interface TimelineTrack {
  id: string;
  name: string;
  type: "dialogue" | "sfx" | "music" | "master";
  order: number;
  volume: number;
  muted: boolean;
  solo: boolean;
  locked: boolean;
  height: number;
  color: string;
}

export interface ImportedAudioEntry {
  id: string;
  filename: string;
  url: string;
  original_name: string;
  duration: number;
  sample_rate: number;
  channels: number;
}

export interface TimelineSnapshot {
  version: number;
  created_at: string;
  tracks: TimelineTrack[];
  clips: TimelineClip[];
}

export interface TimelineData {
  version: number;
  sample_rate: number;
  total_duration: number;
  master_volume: number;
  tracks: TimelineTrack[];
  clips: TimelineClip[];
  imported_audio: ImportedAudioEntry[];
  snapshots: TimelineSnapshot[];
}
