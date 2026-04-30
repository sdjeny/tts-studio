"""
Audio post-processing effects engine.
Adapted from Voicebox (https://github.com/jamiepine/voicebox)
Uses Spotify's pedalboard library for professional-grade DSP effects.

Supported effects: pitch_shift, reverb, delay, chorus, compressor,
                   gain, highpass, lowpass

Usage:
    from app.core.audio_effects import apply_effects_to_file, BUILTIN_PRESETS

    # Apply a built-in preset
    apply_effects_to_file("input.wav", "output.wav", BUILTIN_PRESETS["deep_voice"])

    # Apply custom effects chain
    apply_effects_to_file("input.wav", "output.wav", [
        {"type": "pitch_shift", "enabled": True, "params": {"semitones": -3}},
        {"type": "reverb", "enabled": True, "params": {"room_size": 0.5, "wet_level": 0.3}},
    ])
"""

from __future__ import annotations

import io
import numpy as np
import soundfile as sf
from pathlib import Path
from typing import Any

from pedalboard import (
    Pedalboard,
    Chorus,
    Reverb,
    Compressor,
    Gain,
    HighpassFilter,
    LowpassFilter,
    Delay,
    PitchShift,
)

# ── Effect registry ──────────────────────────────────────

EFFECT_REGISTRY: dict[str, dict[str, Any]] = {
    "pitch_shift": {
        "cls": PitchShift,
        "label": "音调偏移",
        "description": "升高或降低音调（半音）",
        "params": {
            "semitones": {"default": 0.0, "min": -12.0, "max": 12.0, "step": 0.5, "description": "半音偏移量"},
        },
    },
    "reverb": {
        "cls": Reverb,
        "label": "混响",
        "description": "房间混响效果",
        "params": {
            "room_size": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "description": "房间大小"},
            "damping": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "description": "高频阻尼"},
            "wet_level": {"default": 0.33, "min": 0.0, "max": 1.0, "step": 0.01, "description": "湿声比例"},
            "dry_level": {"default": 0.4, "min": 0.0, "max": 1.0, "step": 0.01, "description": "干声比例"},
            "width": {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01, "description": "立体声宽度"},
        },
    },
    "delay": {
        "cls": Delay,
        "label": "回声",
        "description": "延迟/回声效果",
        "params": {
            "delay_seconds": {"default": 0.3, "min": 0.01, "max": 2.0, "step": 0.01, "description": "延迟时间（秒）"},
            "feedback": {"default": 0.3, "min": 0.0, "max": 0.95, "step": 0.01, "description": "反馈量"},
            "mix": {"default": 0.3, "min": 0.0, "max": 1.0, "step": 0.01, "description": "湿声比例"},
        },
    },
    "chorus": {
        "cls": Chorus,
        "label": "合唱/镶边",
        "description": "调制延迟，产生镶边或合唱效果",
        "params": {
            "rate_hz": {"default": 1.0, "min": 0.01, "max": 20.0, "step": 0.01, "description": "LFO 速度（Hz）"},
            "depth": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "description": "调制深度"},
            "feedback": {"default": 0.0, "min": 0.0, "max": 0.95, "step": 0.01, "description": "反馈量"},
            "centre_delay_ms": {"default": 7.0, "min": 0.5, "max": 50.0, "step": 0.1, "description": "中心延迟（ms）"},
            "mix": {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "description": "湿声比例"},
        },
    },
    "compressor": {
        "cls": Compressor,
        "label": "压缩器",
        "description": "动态范围压缩，使音量更均匀",
        "params": {
            "threshold_db": {"default": -20.0, "min": -60.0, "max": 0.0, "step": 0.5, "description": "阈值（dB）"},
            "ratio": {"default": 4.0, "min": 1.0, "max": 20.0, "step": 0.1, "description": "压缩比"},
            "attack_ms": {"default": 10.0, "min": 0.1, "max": 100.0, "step": 0.1, "description": "启动时间（ms）"},
            "release_ms": {"default": 100.0, "min": 10.0, "max": 1000.0, "step": 1.0, "description": "释放时间（ms）"},
        },
    },
    "gain": {
        "cls": Gain,
        "label": "增益",
        "description": "音量调节（dB）",
        "params": {
            "gain_db": {"default": 0.0, "min": -40.0, "max": 40.0, "step": 0.5, "description": "增益（dB）"},
        },
    },
    "highpass": {
        "cls": HighpassFilter,
        "label": "高通滤波",
        "description": "去除低频",
        "params": {
            "cutoff_frequency_hz": {"default": 80.0, "min": 20.0, "max": 8000.0, "step": 1.0, "description": "截止频率（Hz）"},
        },
    },
    "lowpass": {
        "cls": LowpassFilter,
        "label": "低通滤波",
        "description": "去除高频",
        "params": {
            "cutoff_frequency_hz": {"default": 8000.0, "min": 200.0, "max": 20000.0, "step": 1.0, "description": "截止频率（Hz）"},
        },
    },
}

# ── Built-in presets ─────────────────────────────────────

BUILTIN_PRESETS: dict[str, list[dict[str, Any]]] = {
    "deep_voice": [
        {"type": "pitch_shift", "enabled": True, "params": {"semitones": -3.0}},
        {"type": "lowpass", "enabled": True, "params": {"cutoff_frequency_hz": 6000.0}},
        {"type": "compressor", "enabled": True, "params": {"threshold_db": -18.0, "ratio": 3.0, "attack_ms": 10.0, "release_ms": 150.0}},
    ],
    "radio": [
        {"type": "highpass", "enabled": True, "params": {"cutoff_frequency_hz": 300.0}},
        {"type": "lowpass", "enabled": True, "params": {"cutoff_frequency_hz": 3500.0}},
        {"type": "compressor", "enabled": True, "params": {"threshold_db": -15.0, "ratio": 6.0, "attack_ms": 5.0, "release_ms": 50.0}},
        {"type": "gain", "enabled": True, "params": {"gain_db": 6.0}},
    ],
    "echo_chamber": [
        {"type": "reverb", "enabled": True, "params": {"room_size": 0.85, "damping": 0.3, "wet_level": 0.45, "dry_level": 0.55, "width": 1.0}},
        {"type": "delay", "enabled": True, "params": {"delay_seconds": 0.25, "feedback": 0.3, "mix": 0.2}},
    ],
    "robotic": [
        {"type": "chorus", "enabled": True, "params": {"rate_hz": 0.2, "depth": 1.0, "feedback": 0.35, "centre_delay_ms": 7.0, "mix": 0.5}},
    ],
    "telephone": [
        {"type": "highpass", "enabled": True, "params": {"cutoff_frequency_hz": 400.0}},
        {"type": "lowpass", "enabled": True, "params": {"cutoff_frequency_hz": 3200.0}},
        {"type": "compressor", "enabled": True, "params": {"threshold_db": -12.0, "ratio": 8.0, "attack_ms": 2.0, "release_ms": 30.0}},
    ],
    "cave": [
        {"type": "reverb", "enabled": True, "params": {"room_size": 0.95, "damping": 0.2, "wet_level": 0.6, "dry_level": 0.4, "width": 1.0}},
        {"type": "delay", "enabled": True, "params": {"delay_seconds": 0.4, "feedback": 0.4, "mix": 0.25}},
        {"type": "compressor", "enabled": True, "params": {"threshold_db": -20.0, "ratio": 4.0, "attack_ms": 10.0, "release_ms": 100.0}},
    ],
}

# ── Core functions ────────────────────────────────────────

def build_pedalboard(effects_chain: list[dict[str, Any]]) -> Pedalboard:
    """Build a Pedalboard instance from an effects chain config."""
    plugins = []
    for effect in effects_chain:
        if not effect.get("enabled", True):
            continue
        effect_type = effect["type"]
        if effect_type not in EFFECT_REGISTRY:
            continue
        cls = EFFECT_REGISTRY[effect_type]["cls"]
        params = {}
        for pname, pdef in EFFECT_REGISTRY[effect_type]["params"].items():
            params[pname] = effect.get("params", {}).get(pname, pdef["default"])
        plugins.append(cls(**params))
    return Pedalboard(plugins)


def apply_effects(audio: np.ndarray, sample_rate: int, effects_chain: list[dict[str, Any]]) -> np.ndarray:
    """Apply an effects chain to a numpy audio array."""
    if not effects_chain:
        return audio
    board = build_pedalboard(effects_chain)
    if audio.ndim == 1:
        audio_2d = audio[np.newaxis, :]
    else:
        audio_2d = audio
    processed = board(audio_2d.astype(np.float32), sample_rate)
    if audio.ndim == 1:
        return processed[0]
    return processed


def apply_effects_to_file(input_path: str | Path, output_path: str | Path,
                          effects_chain: list[dict[str, Any]]) -> None:
    """Read WAV, apply effects, write WAV."""
    audio, sr = sf.read(str(input_path), dtype="float32")
    processed = apply_effects(audio, sr, effects_chain)
    sf.write(str(output_path), processed, sr)


def apply_effects_to_bytes(audio_bytes: bytes, effects_chain: list[dict[str, Any]]) -> bytes:
    """Apply effects to WAV bytes, return WAV bytes."""
    audio, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
    processed = apply_effects(audio, sr, effects_chain)
    buf = io.BytesIO()
    sf.write(buf, processed, sr, format="WAV")
    return buf.getvalue()


def get_effects_registry() -> list[dict[str, Any]]:
    """Return available effect types with param definitions (for frontend UI)."""
    result = []
    for effect_type, info in EFFECT_REGISTRY.items():
        result.append({
            "type": effect_type,
            "label": info["label"],
            "description": info["description"],
            "params": {name: dict(pdef) for name, pdef in info["params"].items()},
        })
    return result


def get_builtin_presets() -> dict[str, dict[str, Any]]:
    """Return all built-in presets with metadata."""
    return {
        key: {
            "name": _preset_display_name(key),
            "effects_chain": chain,
        }
        for key, chain in BUILTIN_PRESETS.items()
    }


def _preset_display_name(key: str) -> str:
    names = {
        "deep_voice": "低沉",
        "radio": "收音机",
        "echo_chamber": "回声",
        "robotic": "机器人",
        "telephone": "电话",
        "cave": "洞穴",
    }
    return names.get(key, key)


def validate_effects_chain(effects_chain: list[dict[str, Any]]) -> str | None:
    """Validate an effects chain. Returns None if valid, error message otherwise."""
    if not isinstance(effects_chain, list):
        return "effects_chain must be a list"
    for i, effect in enumerate(effects_chain):
        if not isinstance(effect, dict):
            return f"Effect at index {i} must be a dict"
        effect_type = effect.get("type")
        if effect_type not in EFFECT_REGISTRY:
            return f"Unknown effect type '{effect_type}'"
        params = effect.get("params", {})
        if not isinstance(params, dict):
            return f"Effect '{effect_type}' params must be a dict"
        for param_name, value in params.items():
            if param_name not in EFFECT_REGISTRY[effect_type]["params"]:
                return f"Unknown param '{param_name}' for '{effect_type}'"
            pdef = EFFECT_REGISTRY[effect_type]["params"][param_name]
            if not isinstance(value, (int, float)):
                return f"Param '{param_name}' must be a number"
            if value < pdef["min"] or value > pdef["max"]:
                return f"Param '{param_name}' out of range [{pdef['min']}, {pdef['max']}]"
    return None
