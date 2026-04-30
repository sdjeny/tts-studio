import json
import os
import uuid
import time
from pathlib import Path
from typing import Optional

DATA_FILE = Path(os.environ.get("TTS_DATA_FILE", str(Path(__file__).resolve().parent.parent.parent / "data" / "studio.json")))
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

_store_cache: Optional[dict] = None


def _default_store() -> dict:
    return {"projects": []}


def load_store() -> dict:
    global _store_cache
    if _store_cache is not None:
        return _store_cache
    if DATA_FILE.exists():
        try:
            _store_cache = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            return _store_cache
        except Exception:
            pass
    _store_cache = _default_store()
    return _store_cache


def save_store(store: dict) -> None:
    global _store_cache
    _store_cache = store
    DATA_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2), encoding="utf-8")


def new_id(prefix: str = "") -> str:
    ts = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:8]
    return f"{prefix}_{ts}_{uid}" if prefix else f"{ts}_{uid}"