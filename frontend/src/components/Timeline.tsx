import { useState, useEffect, useRef, useCallback } from "react";
import { api, Project } from "../api";

/* ─── inline sub-components ─── */

function TimelineRuler({ duration, zoom, scrollX, currentTime, onSeek }: {
  duration: number; zoom: number; scrollX: number; currentTime: number;
  onSeek: (t: number) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const width = duration * zoom;
  // Determine step: aim for ~100px between marks
  const step = zoom >= 80 ? 0.5 : zoom >= 40 ? 1 : zoom >= 20 ? 2 : zoom >= 10 ? 5 : zoom >= 5 ? 10 : 30;
  const marks: number[] = [];
  for (let t = 0; t <= duration; t += step) marks.push(t);

  const handleClick = (e: React.MouseEvent) => {
    if (!ref.current) return;
    const rect = ref.current.getBoundingClientRect();
    const x = e.clientX - rect.left + scrollX;
    onSeek(Math.max(0, x / zoom));
  };

  return (
    <div ref={ref} onClick={handleClick} style={{
      position: "relative", height: 22, background: "#0c0f18", borderBottom: "1px solid #1e293b",
      overflow: "hidden", cursor: "pointer", flexShrink: 0,
    }}>
      <div style={{ position: "absolute", left: -scrollX, width, height: "100%" }}>
        {marks.map(t => (
          <div key={t} style={{ position: "absolute", left: t * zoom, top: 0, bottom: 0, width: 1, background: "#334155" }}>
            <span style={{ position: "absolute", top: 2, left: 3, fontSize: 9, color: "#64748b", whiteSpace: "nowrap" }}>
              {formatTime(t)}
            </span>
          </div>
        ))}
        {/* playhead */}
        <div style={{
          position: "absolute", left: currentTime * zoom, top: 0, bottom: 0, width: 2, background: "#ef4444", zIndex: 5,
        }} />
      </div>
    </div>
  );
}

function ClipWidget({ clip, zoom, trackHeight, isSelected, onSelect, onMove, onTrimLeft, onTrimRight, onDelete, onDuplicate, onVolumeChange }: {
  clip: any; zoom: number; trackHeight: number; isSelected: boolean;
  onSelect: () => void;
  onMove: (newStart: number) => void;
  onTrimLeft: (offset: number, dur: number) => void;
  onTrimRight: (dur: number) => void;
  onDelete: () => void;
  onDuplicate: () => void;
  onVolumeChange: (v: number) => void;
}) {
  const [dragging, setDragging] = useState<"move" | "left" | "right" | null>(null);
  const dragStart = useRef({ x: 0, start: 0, dur: 0, offset: 0 });
  const leftW = 6; // trim handle width

  const handleMouseDown = (e: React.MouseEvent, mode: "move" | "left" | "right") => {
    e.stopPropagation();
    e.preventDefault();
    onSelect();
    dragStart.current = { x: e.clientX, start: clip.start_time, dur: clip.duration, offset: clip.offset_in_source };
    setDragging(mode);
    const handleMove = (ev: MouseEvent) => {
      const dx = ev.clientX - dragStart.current.x;
      const dt = dx / zoom;
      if (mode === "move") {
        onMove(Math.max(0, dragStart.current.start + dt));
      } else if (mode === "left") {
        const newOffset = Math.max(0, dragStart.current.offset + dt);
        const newDur = Math.max(0.1, dragStart.current.dur - dt);
        onTrimLeft(newOffset, newDur);
      } else if (mode === "right") {
        const newDur = Math.max(0.1, dragStart.current.dur + dt);
        onTrimRight(newDur);
      }
    };
    const handleUp = () => { setDragging(null); window.removeEventListener("mousemove", handleMove); window.removeEventListener("mouseup", handleUp); };
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
  };

  // Color by source
  const sourceType = clip.source_type || "dialogue";
  const borderColor = sourceType === "imported" ? "#a855f6" : isSelected ? "#3b82f6" : "#334155";
  const bgColor = sourceType === "imported" ? "#2e1065" : "#1e293b";
  const textColor = sourceType === "imported" ? "#c4b5fd" : "#94a3b8";
  const volY = (1 - Math.min(clip.volume, 2) / 2) * trackHeight;

  return (
    <div
      onClick={onSelect}
      style={{
        position: "absolute", left: clip.start_time * zoom, top: 2,
        width: Math.max(clip.duration * zoom, 20), height: trackHeight - 4,
        background: bgColor, border: `1px solid ${borderColor}`, borderRadius: 4,
        cursor: dragging ? "grabbing" : "grab", overflow: "hidden", userSelect: "none",
      }}
    >
      {/* Volume line */}
      <div style={{
        position: "absolute", top: volY, left: 0, right: 0, height: 2,
        background: "#3b82f6", opacity: 0.6, pointerEvents: "none",
      }} />

      {/* Left trim handle */}
      <div onMouseDown={e => handleMouseDown(e, "left")} style={{
        position: "absolute", left: 0, top: 0, bottom: 0, width: leftW,
        cursor: "ew-resize", background: isSelected ? "#3b82f644" : "transparent", zIndex: 2,
      }} />

      {/* Right trim handle */}
      <div onMouseDown={e => handleMouseDown(e, "right")} style={{
        position: "absolute", right: 0, top: 0, bottom: 0, width: leftW,
        cursor: "ew-resize", background: isSelected ? "#3b82f644" : "transparent", zIndex: 2,
      }} />

      {/* Center label */}
      <div onMouseDown={e => handleMouseDown(e, "move")} style={{
        position: "absolute", left: leftW, right: leftW, top: 0, bottom: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
        overflow: "hidden", zIndex: 1,
      }}>
        <span style={{ fontSize: 10, color: textColor, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", padding: "0 2px" }}>
          {clip.audio_filename?.slice(0, 12) || clip.id.slice(0, 8)}
        </span>
      </div>

      {/* Duration label */}
      <div style={{
        position: "absolute", bottom: 1, right: leftW + 2, fontSize: 9, color: "#64748b",
        pointerEvents: "none",
      }}>
        {clip.duration.toFixed(1)}s
      </div>

      {/* Hover actions */}
      {isSelected && (
        <div style={{
          position: "absolute", top: 1, right: leftW + 2, display: "flex", gap: 2, zIndex: 3,
        }}>
          <button onClick={e => { e.stopPropagation(); onDuplicate(); }}
            style={{ fontSize: 9, padding: "0 3px", background: "#334155", border: "none", borderRadius: 2, color: "#94a3b8", cursor: "pointer" }}>⧉</button>
          <button onClick={e => { e.stopPropagation(); onDelete(); }}
            style={{ fontSize: 9, padding: "0 3px", background: "#7f1d1d", border: "none", borderRadius: 2, color: "#fca5a5", cursor: "pointer" }}>✕</button>
        </div>
      )}
    </div>
  );
}

function TrackHeader({ track, onUpdate, onDelete }: {
  track: any; onUpdate: (d: any) => void; onDelete: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(track.name);

  return (
    <div style={{
      width: 120, flexShrink: 0, background: "#0f1117", borderRight: "1px solid #1e293b",
      display: "flex", flexDirection: "column", padding: 4, gap: 2,
    }}>
      {editing ? (
        <input value={name} onChange={e => setName(e.target.value)}
          onBlur={() => { onUpdate({ name }); setEditing(false); }}
          onKeyDown={e => { if (e.key === "Enter") { onUpdate({ name }); setEditing(false); } }}
          autoFocus style={{ ...inpS, fontSize: 11, padding: "2px 4px" }} />
      ) : (
        <span onDoubleClick={() => setEditing(true)} style={{ fontSize: 11, color: "#e2e8f0", fontWeight: 600, cursor: "pointer" }}>
          {track.name}
        </span>
      )}
      <div style={{ display: "flex", gap: 2 }}>
        <button onClick={() => onUpdate({ muted: !track.muted })}
          style={{ ...tinyBtn, background: track.muted ? "#7f1d1d" : "transparent", color: track.muted ? "#fca5a5" : "#64748b" }}>
          M
        </button>
        <button onClick={() => onUpdate({ solo: !track.solo })}
          style={{ ...tinyBtn, background: track.solo ? "#854d0e" : "transparent", color: track.solo ? "#fde047" : "#64748b" }}>
          S
        </button>
        <button onClick={() => onUpdate({ locked: !track.locked })}
          style={{ ...tinyBtn, color: track.locked ? "#f59e0b" : "#64748b" }}>
          {track.locked ? "🔒" : "🔓"}
        </button>
        <div style={{ flex: 1 }} />
        <button onClick={onDelete} style={{ ...tinyBtn, color: "#64748b" }}>✕</button>
      </div>
      <input type="range" min={0} max={200} value={Math.round(track.volume * 100)}
        onChange={e => onUpdate({ volume: Number(e.target.value) / 100 })}
        style={{ width: "100%", accentColor: "#3b82f6", height: 12 }} />
      <span style={{ fontSize: 9, color: "#64748b" }}>{Math.round(track.volume * 100)}%</span>
    </div>
  );
}

/* ─── Main Timeline Component ─── */

export default function Timeline({ project, episode, onChange, onError }: {
  project: Project; episode: any; onChange: () => void; onError: (m: string) => void;
}) {
  const [timeline, setTimeline] = useState<any>(null);
  const [zoom, setZoom] = useState(20);
  const [scrollX, setScrollX] = useState(0);
  const [selectedClipId, setSelectedClipId] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [showExport, setShowExport] = useState(false);
  const [showImport, setShowImport] = useState(false);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const sourcesRef = useRef<AudioBufferSourceNode[]>([]);
  const animRef = useRef(0);
  const playStartRef = useRef({ ctxTime: 0, storyTime: 0 });
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Load timeline
  const loadTimeline = useCallback(async () => {
    try {
      const data = await api.getTimeline(project.id, episode.id);
      setTimeline(data.timeline);
    } catch (e: any) { onError(e.message); }
  }, [project.id, episode.id]);

  useEffect(() => { loadTimeline(); }, [loadTimeline]);

  // Auto-assemble
  const assemble = async () => {
    try {
      const gap = timeline ? 0.5 : 0.5;
      const r = await api.assembleTimeline(project.id, episode.id, gap);
      setTimeline(r.timeline);
      onError(`✅ 已装配 ${r.added} 个片段`);
    } catch (e: any) { onError(e.message); }
  };

  // Playback (Web Audio API)
  const stopPlayback = useCallback(() => {
    sourcesRef.current.forEach(s => { try { s.stop(); } catch {} });
    sourcesRef.current = [];
    cancelAnimationFrame(animRef.current);
    setPlaying(false);
  }, []);

  const startPlayback = useCallback(async () => {
    if (!timeline || !timeline.clips.length) return;
    stopPlayback();
    const ctx = audioCtxRef.current || new AudioContext();
    audioCtxRef.current = ctx;
    await ctx.resume();

    // Load all clip audio buffers
    const buffers = new Map<string, AudioBuffer>();
    const uniqueFns = [...new Set(timeline.clips.map((c: any) => c.audio_filename).filter(Boolean))];
    for (const fn of uniqueFns) {
      try {
        const resp = await fetch(`/static/audio/${fn}`);
        const data = await resp.arrayBuffer();
        const buf = await ctx.decodeAudioData(data);
        buffers.set(fn, buf);
      } catch {}
    }

    // Schedule sources
    const master = ctx.createGain();
    master.gain.value = timeline.master_volume || 1;
    master.connect(ctx.destination);

    for (const clip of timeline.clips) {
      const buf = buffers.get(clip.audio_filename);
      if (!buf) continue;
      const src = ctx.createBufferSource();
      src.buffer = buf;
      const gain = ctx.createGain();
      gain.gain.value = clip.volume || 1;
      src.connect(gain);
      gain.connect(master);
      const offset = (clip.offset_in_source || 0);
      const dur = (clip.duration_in_source || clip.duration);
      const when = ctx.currentTime + (clip.start_time - currentTime);
      if (when >= ctx.currentTime) {
        src.start(when, offset, dur);
        sourcesRef.current.push(src);
      }
    }

    playStartRef.current = { ctxTime: ctx.currentTime, storyTime: currentTime };
    setPlaying(true);

    const tick = () => {
      if (!audioCtxRef.current) return;
      const elapsed = audioCtxRef.current.currentTime - playStartRef.current.ctxTime;
      const t = playStartRef.current.storyTime + elapsed;
      setCurrentTime(t);
      // Auto-scroll to keep playhead visible
      if (scrollRef.current) {
        const playheadX = t * zoom;
        const viewLeft = scrollRef.current.scrollLeft;
        const viewRight = viewLeft + scrollRef.current.clientWidth;
        if (playheadX < viewLeft || playheadX > viewRight - 50) {
          scrollRef.current.scrollLeft = playheadX - 100;
        }
      }
      // Auto-stop at end
      const maxEnd = Math.max(...timeline.clips.map((c: any) => c.start_time + c.duration), 0);
      if (t > maxEnd + 0.5) { stopPlayback(); setCurrentTime(0); return; }
      animRef.current = requestAnimationFrame(tick);
    };
    animRef.current = requestAnimationFrame(tick);
  }, [timeline, currentTime, zoom, stopPlayback]);

  const togglePlay = useCallback(() => {
    if (playing) { stopPlayback(); }
    else { startPlayback(); }
  }, [playing, stopPlayback, startPlayback]);

  // Clip operations
  const handleClipMove = async (clipId: string, newStart: number) => {
    try {
      const r = await api.updateTimelineClip(project.id, episode.id, clipId, { start_time: Math.max(0, Math.round(newStart * 100) / 100) });
      setTimeline((prev: any) => prev ? { ...prev, clips: prev.clips.map((c: any) => c.id === clipId ? r.clip : c) } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleTrimLeft = async (clipId: string, offset: number, dur: number) => {
    try {
      const r = await api.updateTimelineClip(project.id, episode.id, clipId, { offset_in_source: Math.round(offset * 100) / 100, duration_in_source: Math.round(dur * 100) / 100 });
      setTimeline((prev: any) => prev ? { ...prev, clips: prev.clips.map((c: any) => c.id === clipId ? r.clip : c) } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleTrimRight = async (clipId: string, dur: number) => {
    try {
      const r = await api.updateTimelineClip(project.id, episode.id, clipId, { duration_in_source: Math.round(dur * 100) / 100 });
      setTimeline((prev: any) => prev ? { ...prev, clips: prev.clips.map((c: any) => c.id === clipId ? r.clip : c) } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleDeleteClip = async (clipId: string) => {
    if (!confirm("删除该片段？")) return;
    try {
      await api.deleteTimelineClip(project.id, episode.id, clipId);
      setTimeline((prev: any) => prev ? { ...prev, clips: prev.clips.filter((c: any) => c.id !== clipId) } : prev);
      setSelectedClipId(null);
    } catch (e: any) { onError(e.message); }
  };

  const handleDuplicateClip = async (clipId: string) => {
    try {
      const r = await api.duplicateTimelineClip(project.id, episode.id, clipId);
      setTimeline((prev: any) => prev ? { ...prev, clips: [...prev.clips, r.clip] } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleClipVolume = async (clipId: string, v: number) => {
    try {
      const r = await api.updateTimelineClip(project.id, episode.id, clipId, { volume: Math.round(v * 100) / 100 });
      setTimeline((prev: any) => prev ? { ...prev, clips: prev.clips.map((c: any) => c.id === clipId ? r.clip : c) } : prev);
    } catch (e: any) { onError(e.message); }
  };

  // Track operations
  const handleAddTrack = async () => {
    const name = prompt("轨道名称:", `轨道 ${(timeline?.tracks?.length || 0) + 1}`);
    if (!name) return;
    const type = prompt("轨道类型 (dialogue/sfx/music):", "dialogue") || "dialogue";
    try {
      const r = await api.addTimelineTrack(project.id, episode.id, name, type);
      setTimeline((prev: any) => prev ? { ...prev, tracks: [...prev.tracks, r.track] } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleUpdateTrack = async (trackId: string, data: any) => {
    try {
      await api.updateTimelineTrack(project.id, episode.id, trackId, data);
      setTimeline((prev: any) => prev ? { ...prev, tracks: prev.tracks.map((t: any) => t.id === trackId ? { ...t, ...data } : t) } : prev);
    } catch (e: any) { onError(e.message); }
  };

  const handleDeleteTrack = async (trackId: string) => {
    if (!confirm("删除该轨道及其所有片段？")) return;
    try {
      await api.deleteTimelineTrack(project.id, episode.id, trackId);
      setTimeline((prev: any) => prev ? {
        ...prev,
        tracks: prev.tracks.filter((t: any) => t.id !== trackId),
        clips: prev.clips.filter((c: any) => c.track_id !== trackId),
      } : prev);
    } catch (e: any) { onError(e.message); }
  };

  // Import audio
  const handleImportFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const r = await api.importTimelineAudio(project.id, episode.id, file);
      setTimeline((prev: any) => prev ? {
        ...prev,
        imported_audio: [...(prev.imported_audio || []), r.audio],
      } : prev);
      onError(`✅ 已导入: ${r.audio.original_name} (${r.audio.duration.toFixed(1)}s)`);
      // Auto-add to a new track if imported audio exists
      if (timeline) {
        const imp = r.audio;
        // Find or create an SFX track
        let sfxTrack = timeline.tracks.find((t: any) => t.type === "sfx" || t.type === "music");
        if (!sfxTrack) {
          const tr = await api.addTimelineTrack(project.id, episode.id, "背景音乐", "music");
          sfxTrack = tr.track;
          setTimeline((prev: any) => prev ? { ...prev, tracks: [...prev.tracks, sfxTrack] } : prev);
        }
        const maxEnd = Math.max(...timeline.clips.map((c: any) => c.start_time + c.duration), 0);
        await api.addTimelineClip(project.id, episode.id, {
          track_id: sfxTrack.id,
          source_type: "imported",
          source_id: imp.id,
          audio_filename: imp.filename,
          offset_in_source: 0,
          duration_in_source: imp.duration,
          start_time: 0,
          duration: imp.duration,
          volume: 0.3,
        });
        await loadTimeline();
      }
    } catch (err: any) { onError(`导入失败: ${err.message}`); }
    e.target.value = "";
  };

  // Normalize
  const handleNormalize = async () => {
    if (!confirm("对所有片段进行音量一致化？这将生成新的标准化音频文件。")) return;
    try {
      const r = await api.normalizeTimeline(project.id, episode.id);
      await loadTimeline();
      onError(`✅ 已标准化 ${r.clips_normalized} 个片段，跳过 ${r.clips_skipped} 个`);
    } catch (e: any) { onError(e.message); }
  };

  // Export
  const handleExport = async (fmt: string = "wav") => {
    try {
      const blob = await api.exportTimeline(project.id, episode.id, { format: fmt, sample_rate: 24000, normalization_db: -20 });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${episode.title || "export"}.${fmt}`;
      a.click();
      URL.revokeObjectURL(url);
      onError("✅ 导出完成");
    } catch (e: any) { onError(e.message); }
  };

  // Snapshot
  const handleSnapshot = async () => {
    try {
      const r = await api.saveTimelineSnapshot(project.id, episode.id);
      onError(`✅ 快照 v${r.version} 已保存`);
    } catch (e: any) { onError(e.message); }
  };

  // Seek
  const handleSeek = (t: number) => {
    const wasPlaying = playing;
    if (wasPlaying) stopPlayback();
    setCurrentTime(Math.max(0, t));
    if (wasPlaying) setTimeout(() => startPlayback(), 50);
  };

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.key === " ") { e.preventDefault(); togglePlay(); }
      if (e.key === "Delete" && selectedClipId) handleDeleteClip(selectedClipId);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [togglePlay, selectedClipId]);

  // Compute dimensions
  const totalDuration = timeline
    ? Math.max(...timeline.clips.map((c: any) => c.start_time + c.duration), 10)
    : 10;
  const timelineWidth = totalDuration * zoom;
  const sortedTracks = timeline ? [...timeline.tracks].sort((a, b) => a.order - b.order) : [];

  return (
    <div style={{ background: "#0a0d14", border: "1px solid #1e293b", borderRadius: 8, overflow: "hidden", marginTop: 12 }}>
      <input ref={fileInputRef} type="file" accept="audio/*" style={{ display: "none" }} onChange={handleImportFile} />

      {/* Toolbar */}
      <div style={{ display: "flex", gap: 4, padding: "6px 8px", background: "#0f1117", borderBottom: "1px solid #1e293b", alignItems: "center", flexWrap: "wrap" }}>
        {!timeline ? (
          <button onClick={assemble} style={btnStyle}>🎬 从对白自动装配</button>
        ) : (
          <>
            <button onClick={assemble} style={btnStyle}>🔄 重新装配</button>
            <button onClick={() => fileInputRef.current?.click()} style={btnStyle}>📥 导入音频</button>
            <button onClick={handleNormalize} style={btnStyle}>🔊 音量一致化</button>
            <button onClick={handleSnapshot} style={btnStyle}>💾 快照</button>
            <button onClick={() => setShowExport(!showExport)} style={{ ...btnStyle, color: "#22c55e", borderColor: "#22c55e" }}>📤 导出</button>
            {showExport && (
              <div style={{ display: "flex", gap: 2 }}>
                <button onClick={() => handleExport("wav")} style={{ ...btnStyle, color: "#22c55e" }}>WAV</button>
              </div>
            )}
          </>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "#64748b" }}>缩放:</span>
        <input type="range" min={5} max={100} value={zoom} onChange={e => setZoom(Number(e.target.value))}
          style={{ width: 80, accentColor: "#3b82f6" }} />
        <span style={{ fontSize: 11, color: "#64748b", minWidth: 30 }}>{zoom}px/s</span>
      </div>

      {/* Transport */}
      <div style={{ display: "flex", gap: 4, padding: "4px 8px", background: "#0c0f18", borderBottom: "1px solid #1e293b", alignItems: "center" }}>
        <button onClick={() => { stopPlayback(); setCurrentTime(0); }} style={btnS}>⏮</button>
        <button onClick={togglePlay} style={{ ...btnS, minWidth: 40 }}>{playing ? "⏸" : "▶"}</button>
        <span style={{ fontSize: 11, color: "#94a3b8", minWidth: 80, fontFamily: "monospace" }}>
          {formatTime(currentTime)} / {formatTime(totalDuration)}
        </span>
        <span style={{ fontSize: 10, color: "#475569" }}>空格播放/暂停，Delete 删除片段</span>
      </div>

      {!timeline ? (
        <div style={{ padding: 40, textAlign: "center", color: "#64748b" }}>
          <p style={{ marginBottom: 12 }}>该剧集尚未创建时间线</p>
          <button onClick={assemble} style={{ ...btnStyle, padding: "8px 20px", fontSize: 14 }}>🎬 从对白自动装配时间线</button>
          <p style={{ marginTop: 8, fontSize: 12, color: "#475569" }}>
            自动将所有已完成音频的对白按顺序排列到同一轨道上
          </p>
        </div>
      ) : (
        <>
          {/* Ruler */}
          <TimelineRuler duration={totalDuration} zoom={zoom} scrollX={scrollX} currentTime={currentTime} onSeek={handleSeek} />

          {/* Tracks area */}
          <div ref={scrollRef} style={{ overflowX: "auto", overflowY: "hidden", position: "relative" }}
            onScroll={e => setScrollX((e.target as HTMLDivElement).scrollLeft)}>
            <div style={{ minWidth: timelineWidth + 120, position: "relative" }}>
              {sortedTracks.map(track => {
                const trackClips = timeline.clips.filter((c: any) => c.track_id === track.id);
                return (
                  <div key={track.id} style={{ display: "flex", borderBottom: "1px solid #1e293b" }}>
                    <TrackHeader track={track} onUpdate={d => handleUpdateTrack(track.id, d)} onDelete={() => handleDeleteTrack(track.id)} />
                    <div style={{
                      position: "relative", height: track.height || 80,
                      width: timelineWidth, flexShrink: 0,
                      background: track.muted ? "#0a0a0a" : "transparent",
                    }}>
                      {/* Track background stripes */}
                      <div style={{
                        position: "absolute", inset: 0,
                        background: `repeating-linear-gradient(90deg, transparent, transparent ${zoom - 1}px, #1e293b08 ${zoom - 1}px, #1e293b08 ${zoom}px)`,
                        pointerEvents: "none",
                      }} />
                      {trackClips.map((clip: any) => (
                        <ClipWidget
                          key={clip.id} clip={clip} zoom={zoom} trackHeight={track.height || 80}
                          isSelected={selectedClipId === clip.id}
                          onSelect={() => setSelectedClipId(clip.id)}
                          onMove={s => handleClipMove(clip.id, s)}
                          onTrimLeft={(o, d) => handleTrimLeft(clip.id, o, d)}
                          onTrimRight={d => handleTrimRight(clip.id, d)}
                          onDelete={() => handleDeleteClip(clip.id)}
                          onDuplicate={() => handleDuplicateClip(clip.id)}
                          onVolumeChange={v => handleClipVolume(clip.id, v)}
                        />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Add track */}
          <div style={{ padding: "4px 8px", borderTop: "1px solid #1e293b" }}>
            <button onClick={handleAddTrack} style={{ ...btnS, fontSize: 11 }}>+ 添加轨道</button>
            {timeline.imported_audio?.length > 0 && (
              <span style={{ fontSize: 11, color: "#64748b", marginLeft: 12 }}>
                已导入 {timeline.imported_audio.length} 个音频文件
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function formatTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 10);
  return `${m}:${sec.toString().padStart(2, "0")}.${ms}`;
}

const btnStyle: React.CSSProperties = {
  background: "transparent", color: "#94a3b8",
  border: "1px solid #334155", borderRadius: 4,
  padding: "3px 8px", cursor: "pointer", fontSize: 11,
};
const btnS: React.CSSProperties = {
  background: "#1e293b", color: "#e2e8f0",
  border: "1px solid #334155", borderRadius: 4,
  padding: "2px 6px", cursor: "pointer", fontSize: 12,
};
const tinyBtn: React.CSSProperties = {
  background: "transparent", border: "1px solid #334155",
  borderRadius: 2, padding: "0 3px", fontSize: 9,
  cursor: "pointer", color: "#64748b",
};
const inpS: React.CSSProperties = {
  background: "#1e293b", border: "1px solid #334155",
  borderRadius: 4, color: "#e2e8f0", outline: "none",
  padding: "4px 8px", fontSize: 13,
};
