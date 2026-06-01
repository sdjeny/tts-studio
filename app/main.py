"""FastAPI entry point for TTS Studio web server."""
import logging
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse

import asyncio
import uuid as _uuid
from app.api import projects, episodes, timeline, voices, config as config_api, task_routes
import app.core.store as _store
from app.core.store import get_project
from app.core.audio_effects import apply_effects_to_file
from app.core import effects_service

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


# ── 初始化 effects_service ─────────────────────────────────
# 注入 DATA_DIR 和 store 引用（启动时一次配置）
effects_service.init(DATA_DIR, _store)


# IR-108: 角色音效批量应用 — 单任务模式（替换旧 per-dialogue 实现）
# 设计说明：一个操作 = 一个任务记录，后台逐条处理并更新进度
# 参照 api_generate_batch_audio 的模式（episodes.py L709-L731）
async def api_apply_effects_single_task(project_id: str, char_id: str):
    """对项目中指定角色的所有对白批量应用音效（单任务模式）。

    Refs #108 — 替换旧 per-dialogue 模式。
    返回单任务记录，通过 TaskPanel 轮询进度。
    """
    from app.core.audio_effects import compute_effects_checksum
    from app.core.task_manager import TaskManager

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
    char_name = char.get("name", "未知角色")

    # 扫描对白统计
    total = 0
    skipped = 0
    data = _store._read()
    for p in data["projects"]:
        if p["id"] != project_id:
            continue
        for ep_in in p["episodes"]:
            for d in ep_in.get("dialogues", []):
                if d.get("character_id") != char_id:
                    continue
                decision = effects_service.decide_dialogue_effect(d, checksum)
                if decision["action"] == "skip":
                    skipped += 1
                total += 1

    if total == 0:
        return {"task_id": "", "status": "noop", "total": 0, "skipped": 0, "char_name": char_name}

    # 获取锁（项目级，跨剧集）
    if not TaskManager.try_acquire(project_id, project_id, "apply_effects"):
        raise HTTPException(409, "该项目已有批量音效应用任务在执行中")

    # 创建单任务记录
    task_id = TaskManager.create(
        project_id=project_id,
        episode_id=project_id,
        task_type="apply_effects",
        total=total,
        extra={
            "char_id": char_id,
            "char_name": char_name,
            "effects_checksum": checksum,
        },
    )

    # 启动后台执行
    asyncio.create_task(
        effects_service.bg_apply_character_effects(
            project_id, char_id, checksum, task_id,
        )
    )

    return {
        "task_id": task_id,
        "status": "running",
        "total": total,
        "skipped": skipped,
        "char_name": char_name,
    }


app.add_api_route(
    "/api/projects/{project_id}/apply-character-effects/{char_id}",
    api_apply_effects_single_task,
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
