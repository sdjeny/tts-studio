"""Timeline audio processing: load, normalize, mix, concatenate.

Uses the existing pedalboard + soundfile + numpy stack.
All functions are pure (no side effects) except file I/O for export.
"""
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Optional

AUDIO_DIR = Path(__file__).resolve().parent.parent / "data" / "audio"

# ── Load ────────────────────────────────────────────────────

def load_audio(filename: str, target_sr: int = 24000) -> tuple:
    """Load audio file, resample to target_sr if needed, convert to mono.
    Returns (audio_np_array, sample_rate).
    """
    path = AUDIO_DIR / filename
    audio, sr = sf.read(str(path), dtype="float32")
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != target_sr:
        ratio = target_sr / sr
        n_samples = int(len(audio) * ratio)
        indices = np.linspace(0, len(audio) - 1, n_samples)
        audio = np.interp(indices, np.arange(len(audio)), audio)
    return audio, target_sr


# ── RMS / Normalization ─────────────────────────────────────

def compute_rms_db(audio: np.ndarray) -> float:
    """RMS energy in dB. Returns -80 for silence."""
    rms = np.sqrt(np.mean(audio ** 2))
    if rms < 1e-10:
        return -80.0
    return float(20 * np.log10(rms))


def normalize_rms(audio: np.ndarray, target_db: float = -20.0) -> np.ndarray:
    """Normalize to target RMS dB. Clips to [-1, 1]."""
    current_db = compute_rms_db(audio)
    if current_db < -70.0:
        return audio
    gain_db = target_db - current_db
    gain_linear = 10 ** (gain_db / 20.0)
    return np.clip(audio * gain_linear, -1.0, 1.0)


# ── Volume + Fades ──────────────────────────────────────────

def apply_volume_and_fades(
    audio: np.ndarray,
    volume: float = 1.0,
    fade_in: float = 0.0,
    fade_out: float = 0.0,
    crossfade_in: float = 0.0,
    crossfade_out: float = 0.0,
    sample_rate: int = 24000,
) -> np.ndarray:
    """Apply volume gain + linear fades + equal-power crossfade curves."""
    result = audio.copy() * volume
    n = len(result)
    if fade_in > 0.0:
        ns = min(int(fade_in * sample_rate), n)
        result[:ns] *= np.linspace(0.0, 1.0, ns)
    if fade_out > 0.0:
        ns = min(int(fade_out * sample_rate), n)
        result[-ns:] *= np.linspace(1.0, 0.0, ns)
    if crossfade_in > 0.0:
        ns = min(int(crossfade_in * sample_rate), n)
        t = np.linspace(0.0, 1.0, ns)
        result[:ns] *= np.sqrt(t)
    if crossfade_out > 0.0:
        ns = min(int(crossfade_out * sample_rate), n)
        t = np.linspace(1.0, 0.0, ns)
        result[-ns:] *= np.sqrt(t)
    return result


# ── Clip Processing ─────────────────────────────────────────

def get_clip_audio(
    audio_filename: str,
    clip: dict,
    timeline_sample_rate: int = 24000,
) -> np.ndarray:
    """Load + trim + effects + volume + fades for one clip.
    Returns processed numpy array.
    """
    audio, sr = load_audio(audio_filename, timeline_sample_rate)
    # Trim
    start_sample = int(clip.get("offset_in_source", 0.0) * sr)
    duration_samples = int(clip.get("duration_in_source", len(audio) / sr) * sr)
    end_sample = min(start_sample + duration_samples, len(audio))
    audio = audio[start_sample:end_sample]
    # Effects chain
    effects_chain = clip.get("effects_chain", [])
    if effects_chain:
        from app.core.audio_effects import apply_effects
        audio = apply_effects(audio, sr, effects_chain)
    # Volume + fades
    audio = apply_volume_and_fades(
        audio,
        volume=clip.get("volume", 1.0),
        fade_in=clip.get("fadeIn", 0.0),
        fade_out=clip.get("fadeOut", 0.0),
        crossfade_in=clip.get("crossfade_in", 0.0),
        crossfade_out=clip.get("crossfade_out", 0.0),
        sample_rate=sr,
    )
    return audio


# ── Multi-track Mix ─────────────────────────────────────────

def mix_timeline(
    tracks: list,
    clips: list,
    sample_rate: int = 24000,
    normalization_target_db: float = -20.0,
) -> tuple:
    """Mix all clips across all tracks into one buffer.
    Returns (mixed_audio_np_array, sample_rate).
    Algorithm: additive mixing → peak normalize → optional RMS normalize.
    """
    # Compute total duration
    total_duration = 0.0
    for clip in clips:
        end = clip["start_time"] + clip["duration"]
        if end > total_duration:
            total_duration = end
    total_samples = int(total_duration * sample_rate) + 1
    master = np.zeros(total_samples, dtype=np.float32)

    has_solo = any(t.get("solo", False) for t in tracks)
    sorted_tracks = sorted(tracks, key=lambda t: t.get("order", 0))

    for track in sorted_tracks:
        if track.get("muted", False):
            continue
        if has_solo and not track.get("solo", False):
            continue
        track_volume = track.get("volume", 1.0)
        for clip in [c for c in clips if c["track_id"] == track["id"]]:
            fn = clip.get("audio_filename")
            if not fn:
                continue
            try:
                clip_audio = get_clip_audio(fn, clip, sample_rate)
            except Exception:
                continue
            clip_audio *= track_volume
            start_sample = int(clip["start_time"] * sample_rate)
            end_sample = start_sample + len(clip_audio)
            if end_sample > len(master):
                master = np.concatenate([master, np.zeros(end_sample - len(master), dtype=np.float32)])
            master[start_sample:end_sample] += clip_audio

    # Peak normalize
    peak = np.max(np.abs(master))
    if peak > 1.0:
        master = master / peak
    # RMS normalize
    if normalization_target_db > -80.0:
        master = normalize_rms(master, normalization_target_db)
    return master, sample_rate


# ── Concatenate (single track) ──────────────────────────────

def concatenate_clips(
    clips_audio: list,
    crossfade_duration: float = 0.0,
    sample_rate: int = 24000,
) -> np.ndarray:
    """Concatenate audio buffers with optional crossfade."""
    if not clips_audio:
        return np.zeros(0, dtype=np.float32)
    if crossfade_duration <= 0.0:
        return np.concatenate(clips_audio)
    cf_samples = int(crossfade_duration * sample_rate)
    result = clips_audio[0]
    for nxt in clips_audio[1:]:
        if cf_samples > 0 and len(result) >= cf_samples and len(nxt) >= cf_samples:
            fo = np.linspace(1.0, 0.0, cf_samples)
            fi = np.linspace(0.0, 1.0, cf_samples)
            overlap = result[-cf_samples:] * fo + nxt[:cf_samples] * fi
            result = np.concatenate([result[:-cf_samples], overlap, nxt[cf_samples:]])
        else:
            result = np.concatenate([result, nxt])
    return result


# ── Export helper ───────────────────────────────────────────

def save_audio(audio: np.ndarray, filename: str, sample_rate: int = 24000) -> Path:
    """Save numpy array to WAV file. Returns filepath."""
    path = AUDIO_DIR / filename
    sf.write(str(path), audio, sample_rate)
    return path
