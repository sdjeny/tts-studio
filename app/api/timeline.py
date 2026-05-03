"""Timeline API: multi-track audio editing for episodes."""
import uuid
import time
import copy
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse

import app.core.store as store
from app.core.timeline_audio import mix_timeline, save_audio, compute_rms_db, load_audio, normalize_rms
from app.api.episodes import _audio_duration, _now, AUDIO_DIR

router = APIRouter()


def _uid() -> str:
    return uuid.uuid4().hex[:12]


def _get_episode_or_404(project_id: str, episode_id: str):
    ep = store.get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    return ep


def _get_timeline_or_404(project_id: str, episode_id: str) -> dict:
    tl = store.get_timeline(project_id, episode_id)
    if not tl:
        raise HTTPException(404, "Timeline not found. Assemble first.")
    return tl


# ── Auto-assemble ───────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/assemble")
async def assemble_timeline(project_id: str, episode_id: str, body: dict = None):
    """Auto-assemble timeline from episode dialogues.
    Creates timeline if not exists; adds new clips if already assembled.
    """
    ep = _get_episode_or_404(project_id, episode_id)
    body = body or {}
    gap = body.get("gap", 0.5)

    # Collect completed dialogues with audio
    dialogues = ep.get("dialogues", [])
    completed = []
    for d in dialogues:
        if d.get("status") != "completed":
            continue
        audio_id = d.get("current_audio_id")
        if not audio_id:
            continue
        audio_rec = None
        for ah in d.get("audio_history", []):
            if ah["id"] == audio_id:
                audio_rec = ah
                break
        if not audio_rec or not audio_rec.get("filename"):
            continue
        dur = audio_rec.get("duration") or _audio_duration(str(AUDIO_DIR / audio_rec["filename"]))
        if dur <= 0:
            dur = _audio_duration(str(AUDIO_DIR / audio_rec["filename"]))
        completed.append({
            "dialogue_id": d["id"],
            "character_name": d.get("character_name", ""),
            "audio_id": audio_id,
            "filename": audio_rec["filename"],
            "duration": dur,
            "text": d.get("text", "")[:30],
        })

    tl = store.get_timeline(project_id, episode_id)
    if tl is None:
        # Create new timeline
        track_id = f"track_{_uid()}"
        tl = {
            "version": 1,
            "sample_rate": 24000,
            "total_duration": 0.0,
            "master_volume": 1.0,
            "tracks": [{
                "id": track_id, "name": "对话", "type": "dialogue",
                "order": 0, "volume": 1.0, "muted": False, "solo": False,
                "locked": False, "height": 80, "color": "#3b82f6",
            }],
            "clips": [],
            "imported_audio": [],
            "snapshots": [],
        }
        store.save_timeline(project_id, episode_id, tl)

    # Build set of existing source_ids to avoid duplicates
    existing_sources = {c.get("source_id") for c in tl["clips"] if c.get("source_type") == "dialogue"}

    track_id = tl["tracks"][0]["id"]
    current_time = 0.0
    if tl["clips"]:
        for c in tl["clips"]:
            end = c["start_time"] + c["duration"]
            if end > current_time:
                current_time = end
        current_time += gap

    added = 0
    for dlg in completed:
        if dlg["dialogue_id"] in existing_sources:
            continue
        clip = {
            "id": f"clip_{_uid()}",
            "track_id": track_id,
            "source_type": "dialogue",
            "source_id": dlg["dialogue_id"],
            "source_audio_id": dlg["audio_id"],
            "audio_filename": dlg["filename"],
            "offset_in_source": 0.0,
            "duration_in_source": dlg["duration"],
            "start_time": current_time,
            "duration": dlg["duration"],
            "volume": 1.0,
            "fadeIn": 0.0, "fadeOut": 0.0,
            "crossfade_in": 0.0, "crossfade_out": 0.0,
            "effects_chain": [],
        }
        store.add_clip_to_timeline(project_id, episode_id, clip)
        current_time += dlg["duration"] + gap
        added += 1

    tl = store.get_timeline(project_id, episode_id)
    tl["total_duration"] = current_time
    tl["version"] = tl.get("version", 0) + 1
    store.save_timeline(project_id, episode_id, tl)
    return {"timeline": tl, "added": added}


# ── Get timeline ────────────────────────────────────────────

@router.get("/projects/{project_id}/episodes/{episode_id}/timeline")
async def get_timeline(project_id: str, episode_id: str):
    _get_episode_or_404(project_id, episode_id)
    tl = store.get_timeline(project_id, episode_id)
    return {"timeline": tl}


# ── Clips CRUD ──────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/clips")
async def add_clip(project_id: str, episode_id: str, body: dict):
    _get_timeline_or_404(project_id, episode_id)
    clip = {
        "id": f"clip_{_uid()}",
        "track_id": body.get("track_id", ""),
        "source_type": body.get("source_type", "dialogue"),
        "source_id": body.get("source_id", ""),
        "source_audio_id": body.get("source_audio_id", ""),
        "audio_filename": body.get("audio_filename", ""),
        "offset_in_source": body.get("offset_in_source", 0.0),
        "duration_in_source": body.get("duration_in_source", 0.0),
        "start_time": body.get("start_time", 0.0),
        "duration": body.get("duration", 0.0),
        "volume": body.get("volume", 1.0),
        "fadeIn": body.get("fadeIn", 0.0),
        "fadeOut": body.get("fadeOut", 0.0),
        "crossfade_in": body.get("crossfade_in", 0.0),
        "crossfade_out": body.get("crossfade_out", 0.0),
        "effects_chain": body.get("effects_chain", []),
    }
    store.add_clip_to_timeline(project_id, episode_id, clip)
    return {"clip": clip}


@router.put("/projects/{project_id}/episodes/{episode_id}/timeline/clips/{clip_id}")
async def update_clip(project_id: str, episode_id: str, clip_id: str, body: dict):
    _get_timeline_or_404(project_id, episode_id)
    updated = store.update_clip_in_timeline(project_id, episode_id, clip_id, **body)
    if not updated:
        raise HTTPException(404, "Clip not found")
    return {"clip": updated}


@router.delete("/projects/{project_id}/episodes/{episode_id}/timeline/clips/{clip_id}")
async def delete_clip(project_id: str, episode_id: str, clip_id: str):
    _get_timeline_or_404(project_id, episode_id)
    if not store.delete_clip_from_timeline(project_id, episode_id, clip_id):
        raise HTTPException(404, "Clip not found")
    return {"ok": True}


@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/clips/{clip_id}/duplicate")
async def duplicate_clip(project_id: str, episode_id: str, clip_id: str):
    tl = _get_timeline_or_404(project_id, episode_id)
    original = None
    for c in tl["clips"]:
        if c["id"] == clip_id:
            original = c
            break
    if not original:
        raise HTTPException(404, "Clip not found")
    new_clip = copy.deepcopy(original)
    new_clip["id"] = f"clip_{_uid()}"
    new_clip["start_time"] = original["start_time"] + original["duration"] + 0.1
    store.add_clip_to_timeline(project_id, episode_id, new_clip)
    return {"clip": new_clip}


@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/clips/{clip_id}/split")
async def split_clip(project_id: str, episode_id: str, clip_id: str, body: dict):
    tl = _get_timeline_or_404(project_id, episode_id)
    original = None
    for c in tl["clips"]:
        if c["id"] == clip_id:
            original = c
            break
    if not original:
        raise HTTPException(404, "Clip not found")
    split_at = body.get("split_time", 0.0)
    if split_at <= 0 or split_at >= original["duration"]:
        raise HTTPException(400, "split_time must be between 0 and clip duration")

    sr = original.get("duration_in_source", original["duration"]) / original["duration"] if original["duration"] > 0 else 1
    first = copy.deepcopy(original)
    second = copy.deepcopy(original)

    first["id"] = f"clip_{_uid()}"
    first["duration"] = split_at
    first["duration_in_source"] = split_at * sr

    second["id"] = f"clip_{_uid()}"
    second["start_time"] = original["start_time"] + split_at
    second["duration"] = original["duration"] - split_at
    second["duration_in_source"] = original["duration_in_source"] - split_at * sr
    second["offset_in_source"] = original["offset_in_source"] + split_at * sr

    store.delete_clip_from_timeline(project_id, episode_id, clip_id)
    store.add_clip_to_timeline(project_id, episode_id, first)
    store.add_clip_to_timeline(project_id, episode_id, second)
    return {"first_clip": first, "second_clip": second}


# ── Tracks CRUD ─────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/tracks")
async def add_track(project_id: str, episode_id: str, body: dict):
    tl = _get_timeline_or_404(project_id, episode_id)
    track = {
        "id": f"track_{_uid()}",
        "name": body.get("name", f"Track {len(tl['tracks']) + 1}"),
        "type": body.get("type", "dialogue"),
        "order": body.get("order", len(tl["tracks"])),
        "volume": body.get("volume", 1.0),
        "muted": False, "solo": False, "locked": False,
        "height": 80,
        "color": body.get("color", "#3b82f6"),
    }
    store.add_track_to_timeline(project_id, episode_id, track)
    return {"track": track}


@router.put("/projects/{project_id}/episodes/{episode_id}/timeline/tracks/{track_id}")
async def update_track(project_id: str, episode_id: str, track_id: str, body: dict):
    _get_timeline_or_404(project_id, episode_id)
    updated = store.update_track_in_timeline(project_id, episode_id, track_id, **body)
    if not updated:
        raise HTTPException(404, "Track not found")
    return {"track": updated}


@router.delete("/projects/{project_id}/episodes/{episode_id}/timeline/tracks/{track_id}")
async def delete_track(project_id: str, episode_id: str, track_id: str):
    _get_timeline_or_404(project_id, episode_id)
    if not store.delete_track_from_timeline(project_id, episode_id, track_id):
        raise HTTPException(400, "Cannot delete track (not found or last track)")
    return {"ok": True}


# ── Import audio ────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/import-audio")
async def import_audio(project_id: str, episode_id: str, file: UploadFile = File(...)):
    _get_timeline_or_404(project_id, episode_id)
    ext = Path(file.filename).suffix.lower()
    if ext not in (".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".webm"):
        raise HTTPException(400, f"Unsupported format: {ext}")

    filename = f"bgm_{_uid()}{ext}"
    filepath = AUDIO_DIR / filename
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        audio, sr = load_audio(filename)
        duration = len(audio) / sr
        channels = 1
    except Exception:
        duration = 0
        channels = 1
        sr = 24000

    entry = {
        "id": f"imp_{_uid()}",
        "filename": filename,
        "url": f"/static/audio/{filename}",
        "original_name": file.filename,
        "duration": round(duration, 2),
        "sample_rate": sr,
        "channels": channels,
    }
    store.add_imported_audio(project_id, episode_id, entry)
    return {"audio": entry}


# ── Normalize ───────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/normalize")
async def normalize_timeline(project_id: str, episode_id: str, body: dict = None):
    """RMS-normalize all clips. Updates clip audio_filename to normalized version."""
    tl = _get_timeline_or_404(project_id, episode_id)
    body = body or {}
    target_db = body.get("target_db", -20.0)
    normalized = 0
    skipped = 0
    for clip in tl["clips"]:
        fn = clip.get("audio_filename")
        if not fn:
            skipped += 1
            continue
        try:
            audio, sr = load_audio(fn)
            rms = compute_rms_db(audio)
            if rms < -70:
                skipped += 1
                continue
            audio = normalize_rms(audio, target_db)
            new_fn = f"norm_{_uid()}.wav"
            save_audio(audio, new_fn, sr)
            store.update_clip_in_timeline(project_id, episode_id, clip["id"],
                                          audio_filename=new_fn, volume=1.0)
            normalized += 1
        except Exception:
            skipped += 1
    return {"clips_normalized": normalized, "clips_skipped": skipped}


# ── Export ──────────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/export")
async def export_timeline(project_id: str, episode_id: str, body: dict = None):
    """Mix timeline to single audio file and return as download."""
    tl = _get_timeline_or_404(project_id, episode_id)
    body = body or {}
    fmt = body.get("format", "wav")
    sr = body.get("sample_rate", 24000)
    norm_db = body.get("normalization_db", -20.0)
    clip_id = body.get("clip_id")

    if not tl["clips"]:
        raise HTTPException(400, "Timeline has no clips")

    if clip_id is not None:
        # Find the clip to determine the export range
        target = None
        for c in tl["clips"]:
            if c["id"] == clip_id:
                target = c
                break
        if target is None:
            raise HTTPException(404, "Clip not found")
        clip_start = target["start_time"]
        clip_end = target["start_time"] + target["duration"]

        # Filter clips overlapping with [clip_start, clip_end]
        filtered = []
        for c in tl["clips"]:
            c_end = c["start_time"] + c["duration"]
            if c["start_time"] < clip_end and c_end > clip_start:
                shifted = copy.deepcopy(c)
                shifted["start_time"] = c["start_time"] - clip_start
                filtered.append(shifted)
        clips_to_mix = filtered
    else:
        clips_to_mix = tl["clips"]

    mixed, sample_rate = mix_timeline(
        tl["tracks"], clips_to_mix,
        sample_rate=sr, normalization_target_db=norm_db,
    )

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    if clip_id is not None:
        out_fn = f"export_clip_{clip_id[:8]}_{timestamp}.{fmt}"
    else:
        out_fn = f"export_{episode_id[:8]}_{timestamp}.{fmt}"
    out_path = save_audio(mixed, out_fn, sample_rate)
    return FileResponse(str(out_path), filename=out_fn, media_type="audio/wav")


# ── Preview (stream) ────────────────────────────────────────

@router.get("/projects/{project_id}/episodes/{episode_id}/timeline/preview")
async def preview_timeline(project_id: str, episode_id: str):
    """Mix timeline and stream as WAV for preview playback."""
    tl = _get_timeline_or_404(project_id, episode_id)
    if not tl["clips"]:
        raise HTTPException(400, "Timeline has no clips")

    import io
    mixed, sr = mix_timeline(tl["tracks"], tl["clips"])
    buf = io.BytesIO()
    import soundfile as sf
    sf.write(buf, mixed, sr, format="WAV")
    buf.seek(0)
    return StreamingResponse(buf, media_type="audio/wav")


# ── Snapshots ───────────────────────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/snapshot")
async def save_snapshot(project_id: str, episode_id: str):
    tl = _get_timeline_or_404(project_id, episode_id)
    version = tl.get("version", 0) + 1
    snapshot = {
        "version": version,
        "created_at": _now(),
        "tracks": copy.deepcopy(tl["tracks"]),
        "clips": copy.deepcopy(tl["clips"]),
    }
    store.add_snapshot(project_id, episode_id, snapshot)
    tl["version"] = version
    store.save_timeline(project_id, episode_id, tl)
    return {"version": version, "created_at": snapshot["created_at"]}


@router.get("/projects/{project_id}/episodes/{episode_id}/timeline/snapshots")
async def list_snapshots(project_id: str, episode_id: str):
    tl = _get_timeline_or_404(project_id, episode_id)
    return {"snapshots": tl.get("snapshots", [])}


@router.post("/projects/{project_id}/episodes/{episode_id}/timeline/snapshots/{version}/restore")
async def restore_snapshot(project_id: str, episode_id: str, version: int):
    _get_timeline_or_404(project_id, episode_id)
    restored = store.restore_snapshot(project_id, episode_id, version)
    if not restored:
        raise HTTPException(404, f"Snapshot version {version} not found")
    return {"timeline": restored}
