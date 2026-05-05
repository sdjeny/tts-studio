"""说话声列表服务 — 四级降级"""
import json
import time
import asyncio
from pathlib import Path

import httpx

_CACHE_PATH = Path("data/voice_cache.json")

# L4: 硬编码兜底（与 _VALID_VOICES 保持一致）
_FALLBACK_SPEAKERS = [
    {"name": "Aiden", "description": "阳光美声中音，清亮通透"},
    {"name": "Dylan", "description": "青春北京男声，清澈自然"},
    {"name": "Eric", "description": "活泼成都男声，略带沙哑的明亮感"},
    {"name": "Ono Anna", "description": "俏皮日式女声，轻盈灵动"},
    {"name": "Ryan", "description": "动感男声，节奏感强"},
    {"name": "Serena", "description": "温柔年轻女声，暖甜细腻"},
    {"name": "Sohee", "description": "温暖韩语女声，情感丰富"},
    {"name": "Uncle Fu", "description": "成熟男声，低沉醇厚"},
    {"name": "Vivian", "description": "明亮年轻女声，略带锐利"},
]

async def get_speakers() -> list[dict]:
    """四级降级获取说话声列表"""
    # L1: 远端 API（HTTP GET /tts/speakers，5s 超时）
    try:
        from app.core.tts import get_client
        client = get_client()
        base_url = client.base_url
        async with httpx.AsyncClient(timeout=5.0) as http:
            resp = await http.get(f"{base_url}/tts/speakers")
            resp.raise_for_status()
            data = resp.json()
            speakers = data.get("speakers", [])
            if speakers:
                _save_cache(speakers)
                return speakers
    except Exception:
        pass

    # L2: 本地缓存
    cached = _load_cache()
    if cached:
        return cached

    # L3: config.yaml
    try:
        import yaml
        from app.core.tts import _tts_dir
        cfg_path = Path(_tts_dir) / "config.yaml"
        if cfg_path.exists():
            cfg = yaml.safe_load(cfg_path.read_text())
            speakers = cfg.get("tts", {}).get("available_speakers")
            if speakers:
                return speakers
    except Exception:
        pass

    # L4: 硬编码兜底
    return _FALLBACK_SPEAKERS


def _save_cache(speakers: list[dict]):
    try:
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_PATH.write_text(json.dumps({
            "updated_at": int(time.time()),
            "speakers": speakers
        }, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _load_cache() -> list[dict] | None:
    try:
        if _CACHE_PATH.exists():
            data = json.loads(_CACHE_PATH.read_text())
            return data.get("speakers")
    except Exception:
        pass
    return None