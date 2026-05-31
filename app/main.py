"""FastAPI entry point for TTS Studio web server."""
import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

import uuid as _uuid
from app.api import projects, episodes, timeline, voices, config as config_api, task_routes
import app.core.store as _store
from app.core.store import get_project
from app.core.audio_effects import apply_effects_to_file

# ── 日志配置 ──────────────────────────────────────────────
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_DIR = DATA_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

log_file = LOG_DIR / "main.log"

class _CleanFormatter(logging.Formatter):
    """把 uvicorn.error / uvicorn.access 等名字映射成干净的标签。"""
    _NAME_MAP = {
        "uvicorn.error":  "uvicorn",
        "uvicorn.access": "access",
        "uvicorn":        "uvicorn",
    }

    def format(self, record: logging.LogRecord) -> str:
        record.name = self._NAME_MAP.get(record.name, record.name)
        return super().format(record)

_fmt = _CleanFormatter(
    "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# 文件 handler
_fh = logging.FileHandler(log_file, encoding="utf-8", mode="a")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(_fmt)

# 控制台 handler
_ch = logging.StreamHandler(sys.stdout)
_ch.setLevel(logging.DEBUG)
_ch.setFormatter(_fmt)

# 根 logger
_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_root.addHandler(_fh)
_root.addHandler(_ch)

# 把 uvicorn 的日志也接进来
for _name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
    _l = logging.getLogger(_name)
    _l.handlers.clear()
    _l.propagate = True

logger = logging.getLogger("tts-studio")
logger.info("日志系统初始化完成，日志文件: %s", log_file)

app = FastAPI(title="TTS Studio", version="1.0")


# ── 请求日志中间件 ─────────────────────────────────────────
@app.middleware("http")
async def log_request(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = (time.time() - start) * 1000
    logger.info(
        "%s %s → %d  (%.1f ms)",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (audio)
AUDIO_DIR = DATA_DIR / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static/audio", StaticFiles(directory=str(AUDIO_DIR)), name="audio")

# API routes
app.include_router(projects.router, prefix="/api")
app.include_router(episodes.router, prefix="/api")
app.include_router(voices.router, prefix="/api")
app.include_router(timeline.router, prefix="/api")
app.include_router(config_api.router, prefix="/api")
app.include_router(task_routes.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def api_apply_effects_to_all(project_id: str, char_id: str):
    """对项目中指定角色的所有对白批量应用当前角色音效链。"""
    from app.core.audio_effects import apply_effects_to_file, compute_effects_checksum
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    char = None
    for c in proj.get("characters", []):
        if c["id"] == char_id:
            char = c
            break
    if not char:
        raise HTTPException(404, "Character not found")

    effects = char.get("audio_effects", [])
    if not effects:
        raise HTTPException(400, "该角色没有配置音效")

    checksum = compute_effects_checksum(effects)

    applied = 0
    skipped = 0
    data = _store._read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep_in in p["episodes"]:
                for d in ep_in.get("dialogues", []):
                    dlg_cid = d.get("character_id")
                    if dlg_cid != char_id:
                        continue
                    current_audio_id = d.get("current_audio_id")
                    if not current_audio_id:
                        skipped += 1
                        continue
                    current_ah = None
                    for ah in d.get("audio_history", []):
                        if ah["id"] == current_audio_id:
                            current_ah = ah
                            break
                    if not current_ah:
                        skipped += 1
                        continue
                    if current_ah.get("effects_source_id") is not None:
                        skipped += 1
                        continue
                    raw_audio_id = current_ah["id"]
                    src_filename = current_ah.get("filename", "")
                    if not src_filename:
                        skipped += 1
                        continue
                    src_path = AUDIO_DIR / src_filename
                    if not src_path.exists():
                        skipped += 1
                        continue

                    existing_fx = None
                    for ah in d.get("audio_history", []):
                        if (ah.get("effects_source_id") == raw_audio_id
                                and ah.get("effects_checksum") is not None):
                            existing_fx = ah
                            break

                    if existing_fx and existing_fx.get("effects_checksum") == checksum:
                        d["current_audio_id"] = existing_fx["id"]
                        d["status"] = "completed"
                        applied += 1
                        continue

                    new_filename = f"fx_{_uuid.uuid4().hex[:8]}.wav"
                    new_filepath = AUDIO_DIR / new_filename
                    try:
                        apply_effects_to_file(str(src_path), str(new_filepath), effects)
                    except Exception:
                        skipped += 1
                        continue
                    new_id = f"audio_{_uuid.uuid4().hex[:8]}"
                    audio_url = f"/static/audio/{new_filename}"
                    from app.api.episodes import _audio_duration
                    d["audio_history"].append({
                        "id": new_id,
                        "url": audio_url,
                        "filename": new_filename,
                        "created_at": _store._now(),
                        "effects_source_id": raw_audio_id,
                        "effects_checksum": checksum,
                        "duration": _audio_duration(str(new_filepath)),
                    })
                    d["current_audio_id"] = new_id
                    d["status"] = "completed"
                    applied += 1
            _store._write(data)
            return {"applied": applied, "skipped": skipped}

    raise HTTPException(500, "更新数据失败")


app.add_api_route(
    "/api/projects/{project_id}/apply-character-effects/{char_id}",
    api_apply_effects_to_all,
    methods=["POST"],
)


# Serve frontend
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        if full_path.startswith(("api/", "static/", "docs", "openapi")):
            return HTMLResponse(content="<html><body>Not Found</body></html>", status_code=404)
        return FileResponse(str(FRONTEND_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
