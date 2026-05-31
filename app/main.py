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


# #103: 对白音效应用决策函数 — 定位→对比→决策
# 根据 #100 设计：effects_source_id 定位原音血缘，effects_checksum 判断音效链是否变更
def _decide_dialogue_effect(dialogue: dict, checksum: str) -> dict:
    """对单个对白执行「定位→对比→决策」。

    对应 Issue: #103
    设计说明: 根据 #100 的 effects_source_id + effects_checksum 设计，
    判断对白是否需要重新应用音效。返回 action=skip/process，process 时带 mode。

    Args:
        dialogue: 对白对象（含 current_audio_id, audio_history）
        checksum: 当前角色音效链的 MD5 校验码

    Returns:
        {"action": "skip"} — 无需处理
        {"action": "process", "mode": "create"|"add"|"replace", "raw_audio_id": str|None}
    """
    current_audio_id = dialogue.get("current_audio_id")
    if not current_audio_id:
        # 无音频：后续生成时自动用角色音效，但先创建任务占位
        return {"action": "process", "mode": "create", "raw_audio_id": None}

    audio_history = dialogue.get("audio_history", [])
    current_ah = next((ah for ah in audio_history if ah["id"] == current_audio_id), None)
    if not current_ah:
        return {"action": "skip"}

    effects_source_id = current_ah.get("effects_source_id")

    if effects_source_id is not None:
        # 当前已是效果音 — Bug #103 修复：必须对比 checksum，不能直接跳过
        if current_ah.get("effects_checksum") == checksum:
            # 音效链没变，跳过
            return {"action": "skip"}
        else:
            # #103 Bug 修复：checksum 不同，需要替换效果音
            # effects_source_id 指向原音 ID
            raw_id = current_ah.get("effects_source_id")
            return {"action": "process", "mode": "replace", "raw_audio_id": raw_id}
    else:
        # 当前是原音（effects_source_id is None）
        # 检查是否已有附加效果音记录
        existing_fx = next(
            (ah for ah in audio_history
             if ah.get("effects_source_id") == current_audio_id
             and ah.get("effects_checksum") is not None),
            None
        )
        if existing_fx and existing_fx.get("effects_checksum") == checksum:
            # 已有相同 checksum 的效果音，跳过
            return {"action": "skip"}
        else:
            # 首次附加效果音或 checksum 不同
            return {"action": "process", "mode": "add", "raw_audio_id": current_audio_id}


# #103: 重写为异步批量创建后台任务
# 旧版 bug: 1) 无音频对白直接跳过 2) effects_source_id!=null 直接跳过不对比 checksum
# 新版: 遍历所有对白 → 决策 → 创建后台任务 → 异步串行执行
async def api_apply_effects_to_all(project_id: str, char_id: str):
    """对项目中指定角色的所有对白批量创建音效应用后台任务。

    对应 Issue: #103
    设计说明: 改为异步模式 — 同步遍历对白创建任务，后台串行执行音频处理。
    每个对白独立一个任务，可在后台任务面板查看进度。

    Args:
        project_id: 项目 ID
        char_id: 角色 ID
    Returns:
        {"task_ids": [...], "total": N, "skipped": M}
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

    task_ids = []
    skipped = 0
    data = _store._read()
    for p in data["projects"]:
        if p["id"] != project_id:
            continue
        for ep_in in p["episodes"]:
            for d in ep_in.get("dialogues", []):
                if d.get("character_id") != char_id:
                    continue

                decision = _decide_dialogue_effect(d, checksum)
                if decision["action"] == "skip":
                    skipped += 1
                    continue

                # 创建后台任务，extra 携带执行所需全部信息
                task_id = TaskManager.create(
                    project_id=project_id,
                    episode_id=ep_in["id"],
                    task_type="apply_effects",
                    total=1,
                    extra={
                        "dialogue_id": d["id"],
                        "character_id": char_id,
                        "effects_checksum": checksum,
                        "effects_chain": effects,
                        "mode": decision["mode"],
                        "raw_audio_id": decision["raw_audio_id"],
                    },
                )
                task_ids.append(task_id)

    # 后台启动串行执行（不阻塞 API 返回）
    if task_ids:
        asyncio.create_task(_run_tasks_with_lock(project_id, task_ids))

    return {
        "task_ids": task_ids,
        "total": len(task_ids),
        "skipped": skipped,
    }


# #103: 使用项目锁串行执行音效应用任务，避免并发写同一数据
async def _run_tasks_with_lock(project_id: str, task_ids: list):
    """使用项目锁串行执行音效应用任务。

    对应 Issue: #103
    设计说明: 通过 TaskManager.get_project_lock 获取项目级 asyncio.Lock，
    确保同一项目的音效任务串行执行，避免并发读写 store.json。
    """
    from app.core.task_manager import TaskManager
    lock = TaskManager.get_project_lock(project_id)
    async with lock:
        for tid in task_ids:
            await _execute_apply_effect_task(project_id, tid)


# #103: 单个对白音效应用任务的后台执行器
# 三种模式: add(新增效果音) / replace(替换旧效果音) / create(无音频占位)
async def _execute_apply_effect_task(project_id: str, task_id: str):
    """单个对白音效应用任务的后台执行器。

    对应 Issue: #103
    设计说明: 从任务 extra 字段读取对白信息，定位原音文件，应用音效链生成新音频。
    replace 模式会删除旧效果音文件并原地更新 audio_history 记录。
    add 模式追加新记录到 audio_history。

    Args:
        project_id: 项目 ID
        task_id: 任务 ID
    """
    from app.core.task_manager import TaskManager
    from app.core.audio_effects import apply_effects_to_file
    from app.api.episodes import _audio_duration

    task = TaskManager.get(project_id, task_id)
    if not task:
        return
    extra = task.get("extra", {})
    dialogue_id = extra["dialogue_id"]
    mode = extra["mode"]
    raw_audio_id = extra["raw_audio_id"]
    effects_chain = extra["effects_chain"]
    checksum = extra["effects_checksum"]

    try:
        # #103 Review A-1: Step 1 — atomic_update 外读取对白信息和原音路径
        project = _store.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")
        episode_id = task["episode_id"]
        episode = next(
            (ep for ep in project.get("episodes", []) if ep["id"] == episode_id), None
        )
        if not episode:
            raise ValueError("剧集不存在")
        dialogue = next(
            (d for d in episode.get("dialogues", []) if d["id"] == dialogue_id), None
        )
        if not dialogue:
            raise ValueError("对白不存在")

        # create 模式 — 无音频时标记 error；有音频时降级为 add
        if mode == "create":
            if not dialogue.get("current_audio_id"):
                raise ValueError("对白没有音频，无法应用音效")
            mode = "add"
            raw_audio_id = dialogue["current_audio_id"]

        # 定位原音文件
        audio_history = dialogue.get("audio_history", [])
        src_ah = next(
            (ah for ah in audio_history if ah["id"] == raw_audio_id), None
        )
        if not src_ah:
            raise ValueError("原音记录不存在")
        src_filename = src_ah.get("filename", "")
        if not src_filename:
            raise ValueError("原音文件名缺失")
        src_path = AUDIO_DIR / src_filename
        if not src_path.exists():
            raise ValueError("原音文件不存在")

        # replace 模式：查找旧效果音记录并删除旧文件
        old_fx_id = None
        if mode == "replace":
            old_fx = next(
                (ah for ah in audio_history
                 if ah.get("effects_source_id") == raw_audio_id
                 and ah.get("effects_checksum") is not None),
                None
            )
            if old_fx and old_fx.get("filename"):
                old_file = AUDIO_DIR / old_fx["filename"]
                if old_file.exists():
                    old_file.unlink()
            if old_fx:
                old_fx_id = old_fx["id"]

        # #103 Review A-1: Step 2 — 线程池中执行 CPU 密集的音频处理
        new_filename = f"fx_{_uuid.uuid4().hex[:8]}.wav"
        new_filepath = AUDIO_DIR / new_filename
        await asyncio.to_thread(
            apply_effects_to_file, str(src_path), str(new_filepath), effects_chain
        )
        new_duration = _audio_duration(str(new_filepath))

        # #103 Review A-1: Step 3 — atomic_update 内仅做数据写入
        async with _store.atomic_update() as data:
            # 重新定位 dialogue（数据可能已变更）
            dialogue = None
            for p in data["projects"]:
                if p["id"] != project_id:
                    continue
                for ep_in in p["episodes"]:
                    if ep_in["id"] != episode_id:
                        continue
                    for d in ep_in.get("dialogues", []):
                        if d["id"] == dialogue_id:
                            dialogue = d
                            break
            if not dialogue:
                raise ValueError("atomic_update 中对白不存在")

            if old_fx_id:
                # replace 模式：原地更新记录
                for ah in dialogue.get("audio_history", []):
                    if ah["id"] == old_fx_id:
                        ah["filename"] = new_filename
                        ah["url"] = f"/static/audio/{new_filename}"
                        ah["duration"] = new_duration
                        ah["effects_checksum"] = checksum
                        break
                new_id = old_fx_id
            else:
                # add 模式：追加新记录
                new_id = f"audio_{_uuid.uuid4().hex[:8]}"
                dialogue["audio_history"].append({
                    "id": new_id,
                    "url": f"/static/audio/{new_filename}",
                    "filename": new_filename,
                    "created_at": _store._now(),
                    "effects_source_id": raw_audio_id,
                    "effects_checksum": checksum,
                    "duration": new_duration,
                })

            dialogue["current_audio_id"] = new_id
            dialogue["status"] = "completed"

        TaskManager.update(project_id, task_id, status="complete", current=1)

    except Exception as e:
        logger.error("音效应用任务失败 [%s]: %s", task_id, e)
        TaskManager.update(project_id, task_id, status="error", error=str(e))


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
