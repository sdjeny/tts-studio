"""Episode & Dialogue CRUD API."""
import asyncio
import io
import json
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from app.core.store import (
    get_project, project_episodes, get_episode, create_episode,
    update_episode, delete_episode, episode_dialogues, add_dialogue,
    update_dialogue, delete_dialogue, add_audio_to_history,
    clear_audio_history, update_dialogue_status,
    set_current_audio, remove_audio_from_history,
    _now,
)
import app.core.store as store

router = APIRouter()

AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

# 每项目生成锁：防止多集串行提交时数据竞争
_gen_locks: dict[str, asyncio.Lock] = {}


def _build_chars_info(proj: dict, detailed: bool = False) -> list[str]:
    """构建角色信息列表（仅真实角色）。
    detailed=True 时包含 base_instruct（用于对白/大纲生成），False 时只有基础信息。
    """
    chars = list(proj.get("characters", []))
    result = []
    for c in chars:
        if detailed:
            base_instruct = c.get("base_instruct", "")
            desc = c.get("description", "无")
            result.append(
                f"- {c['name']} (voice: {c.get('voice_id', '默认')}, "
                f"基础风格: {base_instruct or '无'}, "
                f"性格/描述: {desc})"
            )
        else:
            result.append(f"- {c['name']} (voice: {c.get('voice_id', '默认')}, 描述: {c.get('description', '无')})")
    return result



def _audio_duration(filepath: str) -> float:
    """读取音频文件时长（秒），失败返回 0。"""
    try:
        import soundfile as sf
        info = sf.info(filepath)
        return round(info.duration, 2)
    except Exception:
        return 0.0


# ── schemas ────────────────────────────────────────────

class EpisodeCreate(BaseModel):
    title: str


class EpisodeUpdate(BaseModel):
    title: str = ""
    summary: str = ""
    style_enabled: bool | None = None


class DialogueCreate(BaseModel):
    character_id: str
    text: str
    instruct: str = ""
    order: int = 0


class DialogueUpdate(BaseModel):
    character_id: str | None = None
    text: str | None = None
    instruct: str | None = None
    style_enabled: bool | None = None
    order: int | None = None


class DialogueInsert(BaseModel):
    after_dialogue_id: str
    character_id: str = ""
    text: str = ""
    instruct: str = ""


class BatchDialogueCreate(BaseModel):
    character_id: str
    text: str
    instruct: str = ""
    order: int = 0


# ── episode endpoints ──────────────────────────────────

@router.get("/projects/{project_id}/episodes")
async def api_list_episodes(project_id: str):
    return project_episodes(project_id)


@router.post("/projects/{project_id}/episodes")
async def api_create_episode(project_id: str, body: EpisodeCreate):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    return create_episode(project_id, body.title)


@router.patch("/projects/{project_id}/episodes/{episode_id}")
async def api_update_episode(project_id: str, episode_id: str, body: EpisodeUpdate):
    fields = {}
    if body.title:
        fields["title"] = body.title
    if body.summary:
        fields["summary"] = body.summary
    if body.style_enabled is not None:
        fields["style_enabled"] = body.style_enabled
    if not fields:
        raise HTTPException(400, "没有要更新的字段")
    ep = update_episode(project_id, episode_id, **fields)
    if not ep:
        raise HTTPException(404, "Episode not found")
    # 同步更新所有对白的 style_enabled
    if body.style_enabled is not None:
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == episode_id:
                            for d in ep_in["dialogues"]:
                                d["style_enabled"] = body.style_enabled
                            break
                    break
    return ep


@router.delete("/projects/{project_id}/episodes/{episode_id}")
async def api_delete_episode(project_id: str, episode_id: str):
    if not delete_episode(project_id, episode_id):
        raise HTTPException(404, "Episode not found")
    return {"ok": True}


# ── dialogue endpoints ─────────────────────────────────

@router.delete("/projects/{project_id}/episodes/{episode_id}/purge-dialogues")
async def api_purge_episode_dialogues(project_id: str, episode_id: str):
    """清空剧集所有对白：删除该剧集所有对白及其关联音频文件（不可逆）。"""
    from app.core.store import delete_episode_all_dialogues
    ok, dlg_count, deleted_files = delete_episode_all_dialogues(project_id, episode_id)
    if not ok:
        raise HTTPException(404, "Episode not found")
    return {"ok": True, "deleted_dialogues": dlg_count, "deleted_files": deleted_files}


@router.get("/projects/{project_id}/episodes/{episode_id}/dialogues")
async def api_list_dialogues(project_id: str, episode_id: str):
    return episode_dialogues(project_id, episode_id)


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues")
async def api_add_dialogue(project_id: str, episode_id: str, body: DialogueCreate):
    if not get_episode(project_id, episode_id):
        raise HTTPException(404, "Episode not found")
    return add_dialogue(project_id, episode_id, body.character_id, body.text, body.order, body.instruct or "")


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/batch")
async def api_batch_add_dialogues(project_id: str, episode_id: str, body: list[BatchDialogueCreate]):
    if not get_episode(project_id, episode_id):
        raise HTTPException(404, "Episode not found")
    results = []
    for i, item in enumerate(body):
        dlg = add_dialogue(project_id, episode_id, item.character_id, item.text, item.order or i, item.instruct)
        if dlg:
            results.append(dlg)
    return results


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/reorder")
async def api_reorder_dialogues(project_id: str, episode_id: str):
    """重建整个 episode 的 order 连续性。用于修复历史遗留的 order 重复问题。"""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    count = store.reorder_episode_dialogues(project_id, episode_id)
    return {"ok": True, "dialogues": count}


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/insert")
async def api_insert_dialogue(project_id: str, episode_id: str, body: DialogueInsert):
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    new_dlg, affected = store.insert_dialogue_after(
        project_id, episode_id, body.after_dialogue_id,
        body.character_id, body.text, body.instruct
    )
    if new_dlg is None:
        raise HTTPException(404, "Target dialogue not found")
    return {"ok": True, "dialogue": new_dlg, "affected": affected}


@router.patch("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}")
async def api_update_dialogue(project_id: str, episode_id: str, dialogue_id: str, body: DialogueUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "没有要更新的字段")
    dlg = update_dialogue(project_id, episode_id, dialogue_id, **fields)
    if not dlg:
        raise HTTPException(404, "Dialogue not found")
    return dlg


@router.patch("/projects/{project_id}/episodes/{episode_id}/dialogues/batch-style")
async def api_batch_update_dialogue_style(project_id: str, episode_id: str, body: EpisodeUpdate):
    """批量更新剧集所有对白的 style_enabled。"""
    if body.style_enabled is None:
        raise HTTPException(400, "style_enabled 不能为空")
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    async with store.atomic_update() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                for ep_in in p["episodes"]:
                    if ep_in["id"] == episode_id:
                        for d in ep_in["dialogues"]:
                            d["style_enabled"] = body.style_enabled
                        return {"ok": True, "updated": len(ep_in["dialogues"])}
                break
    raise HTTPException(404, "Episode not found")


@router.delete("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}")
async def api_delete_dialogue(project_id: str, episode_id: str, dialogue_id: str):
    """Delete a dialogue and all its audio files."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    # Delete audio files on disk
    for d in ep.get("dialogues", []):
        if d["id"] == dialogue_id:
            for ah in d.get("audio_history", []):
                fn = ah.get("filename", "")
                if fn:
                    fp = AUDIO_DIR / fn
                    if fp.exists():
                        os.remove(str(fp))
            break
    if not delete_dialogue(project_id, episode_id, dialogue_id):
        raise HTTPException(404, "Dialogue not found")
    return {"ok": True}


@router.delete("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/purge")
async def api_purge_dialogue(project_id: str, episode_id: str, dialogue_id: str):
    """清空对白：删除该条对白及其所有音频文件（不可逆）。"""
    from app.core.store import delete_dialogue_and_audio_files
    ok, deleted = delete_dialogue_and_audio_files(project_id, episode_id, dialogue_id)
    if not ok:
        raise HTTPException(404, "Dialogue not found")
    return {"ok": True, "deleted_files": deleted}


# ── audio / TTS endpoints ──────────────────────────────

from app.core.tts import submit_tts, check_tts_status
from app.core.tts import get_client
from datetime import datetime


def _get_project_tts_defaults(project_id: str) -> dict:
    """
    读取项目的 tts_defaults，返回可透传给 submit_tts 的采样参数字典。
    若项目无 tts_defaults（旧数据未迁移），返回空 dict，
    此时 submit_tts → TTS 服务端将使用其内置保守默认值。
    """
    proj = get_project(project_id)
    if not proj:
        return {}
    defaults = proj.get("tts_defaults", {})
    # 仅提取 submit_tts 能识别的参数，过滤掉 None 和未知字段
    keys = ("temperature", "do_sample", "top_k", "top_p", "repetition_penalty")
    return {k: defaults[k] for k in keys if k in defaults and defaults[k] is not None}


def _resolve_dialogue_tts_params(project_id: str, dlg: dict, proj: dict = None) -> dict:
    """
    统一解析对白的 TTS 调用参数。所有生成路径（单条、批量、重试）共用此函数，
    确保角色查找、voice_id 校验、instruct 组合、style_enabled 开关、
    项目级 tts_defaults 读取等逻辑完全一致，消除代码克隆。

    返回 dict 可直接 ** 展开传入 submit_tts()：
        {text, speaker, instruct, speed, pitch, temperature, do_sample, top_k, top_p, repetition_penalty}

    角色查找仅使用项目真实角色列表，不再有虚拟角色（旁白/场景）fallback。
    若角色不存在会自动创建（兜底）。
    """
    if proj is None:
        proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    # ── 角色查找（真实角色） ──────────────────────────────
    char = None
    char_id = dlg["character_id"]
    # 查找真实角色
    for c in proj.get("characters", []):
        if c["id"] == char_id:
            char = c
            break
    # 角色不存在时自动创建（兜底，防止预处理遗漏导致卡死）
    if not char:
        from app.core.store import add_character
        char_name = dlg.get("character_name") or char_id
        existing = next((c for c in proj["characters"] if c["name"] == char_name), None)
        if existing:
            char = existing
        else:
            char = add_character(
                project_id, char_name, voice_id="",
                description=f"自动创建角色（原 ID: {char_id}），可在角色面板修改音色",
            )
            if char:
                proj["characters"].append(char)
    if not char:
        raise HTTPException(400, f"角色不存在（character_id: {char_id}），请先在角色管理中创建角色或修改对白的角色设置")

    # ── voice_id 安全校验 ──────────────────────────────
    voice_id = char.get("voice_id", "")

    # ── instruct 组合（受 style_enabled 开关控制） ──────
    base_instruct = char.get("base_instruct", "")
    scene_instruct = dlg.get("instruct", "")
    style_enabled = dlg.get("style_enabled", False)
    if style_enabled:
        full_instruct = f"{base_instruct}，{scene_instruct}" if base_instruct and scene_instruct else (base_instruct or scene_instruct)
    else:
        full_instruct = base_instruct  # 仅角色基础风格，忽略场景情绪

    # ── 项目级 TTS 采样参数 ────────────────────────────
    tts_params = _get_project_tts_defaults(project_id)

    return {
        "text": dlg["text"],
        "speaker": voice_id,
        "instruct": full_instruct,
        "speed": char.get("speed", 1.0),
        "pitch": char.get("pitch", 1.0),
        **tts_params,
    }


async def _download_and_save(project_id: str, episode_id: str, dialogue_id: str,
                             task_id: str, placeholder_id: str):
    """Background task: check TTS status once, download if done, otherwise leave for manual refresh."""
    try:
        result = await check_tts_status(task_id)

        if result["status"] in ("pending", "processing"):
            # 还没完成，不轮询，等用户手动刷新
            return

        if result["status"] == "failed":
            raise Exception(result["error"] or "TTS 任务失败")

        # status == success，下载音频
        client = get_client()
        loop = asyncio.get_event_loop()

        def _dl():
            return client.download(task_id)

        dl_result = await loop.run_in_executor(None, _dl)
        if not dl_result.ok:
            raise Exception(f"TTS download failed: {dl_result.error}")

        # 保存原始音频（不应用音效，raw=True）
        audio_data = dl_result.data
        filename = f"{task_id}.wav"
        filepath = AUDIO_DIR / filename
        with open(filepath, "wb") as f:
            f.write(audio_data)
        audio_url = f"/static/audio/{filename}"
        is_raw = True

        # Replace placeholder with real record
        real_id = f"audio_{uuid.uuid4().hex[:8]}"
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == episode_id:
                            for d in ep_in["dialogues"]:
                                if d["id"] == dialogue_id:
                                    d["audio_history"] = [
                                        a for a in d["audio_history"]
                                        if a.get("id") != placeholder_id
                                    ]
                                    d["audio_history"].append({
                                        "id": real_id,
                                        "url": audio_url,
                                        "filename": filename,
                                        "created_at": _now(),
                                        "raw": is_raw,
                                        "duration": _audio_duration(str(filepath)),
                                    })
                                    d["current_audio_id"] = real_id
                                    d["status"] = "completed"
                                    return
                            break
                    break
    except Exception as e:
        # 系统端异常（超时/网络/下载失败）→ 保持 generating 状态，等用户刷新重试
        # 只有 TTS 服务器明确返回 failed 才算真正失败（在 check_tts_status 里判断）
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == episode_id:
                            for d in ep_in["dialogues"]:
                                if d["id"] == dialogue_id:
                                    # 更新占位记录：保留 task_id，标记 interrupted 便于前端提示
                                    for a in d["audio_history"]:
                                        if a.get("id") == placeholder_id:
                                            a["interrupted"] = True
                                            a["error"] = str(e)
                                            break
                                    d["status"] = "generating"
                                    return
                            break
                    break


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/generate")
async def api_generate_audio(project_id: str, episode_id: str, dialogue_id: str):
    """Fire-and-forget: submit TTS, return immediately with 'generating' status."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    dlg = None
    for d in ep["dialogues"]:
        if d["id"] == dialogue_id:
            dlg = d
            break
    if not dlg:
        raise HTTPException(404, "Dialogue not found")

    proj = get_project(project_id)

    # 统一解析 TTS 参数（角色查找 + voice_id + instruct + style_enabled + tts_defaults）
    tts_kwargs = _resolve_dialogue_tts_params(project_id, dlg, proj)

    # Submit TTS, get task_id immediately
    try:
        task_id = await submit_tts(**tts_kwargs)
    except Exception as e:
        # Submit 失败（网络/TTS服务不可用）→ 写 interrupted 占位，等刷新时重新提交
        interrupt_id = f"gen_{uuid.uuid4().hex[:8]}"
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == episode_id:
                            for d in ep_in["dialogues"]:
                                if d["id"] == dialogue_id:
                                    d["audio_history"].append({
                                        "id": interrupt_id,
                                        "url": "",
                                        "filename": "",
                                        "created_at": _now(),
                                        "status": "generating",
                                        "interrupted": True,
                                        "error": str(e),
                                    })
                                    d["current_audio_id"] = interrupt_id
                                    d["status"] = "generating"
                                    return d
                            break
                    break
        raise HTTPException(504, f"TTS服务不可用: {e}")

    # Write placeholder with task_id, return immediately
    placeholder_id = f"gen_{uuid.uuid4().hex[:8]}"
    async with store.atomic_update() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                for ep_in in p["episodes"]:
                    if ep_in["id"] == episode_id:
                        for d in ep_in["dialogues"]:
                            if d["id"] == dialogue_id:
                                d["audio_history"].append({
                                    "id": placeholder_id,
                                    "url": "",
                                    "filename": "",
                                    "created_at": _now(),
                                    "status": "generating",
                                    "task_id": task_id,
                                })
                                d["current_audio_id"] = placeholder_id
                                d["status"] = "generating"
                                break
                        break
                break

    # Kick off background download
    asyncio.create_task(
        _download_and_save(project_id, episode_id, dialogue_id, task_id, placeholder_id)
    )

    # Return immediately — frontend will show "生成中..."
    d = get_episode(project_id, episode_id)
    for dlg_item in d["dialogues"]:
        if dlg_item["id"] == dialogue_id:
            return dlg_item
    raise HTTPException(404, "Dialogue not found")


class BatchAudioRequest(BaseModel):
    dialogue_ids: list[str]


class BatchRefreshRequest(BaseModel):
    dialogue_ids: list[str]


@router.post("/projects/{project_id}/episodes/{episode_id}/refresh-batch")
async def api_batch_refresh_dialogues(project_id: str, episode_id: str, body: BatchRefreshRequest):
    """批量刷新对白状态，后台任务模式。"""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    total = len(body.dialogue_ids)
    from app.core.store import init_generation_task
    from app.core.dialogue_service import run_batch_refresh
    task_id = init_generation_task(project_id, episode_id, "refresh", total=total)
    asyncio.create_task(run_batch_refresh(project_id, episode_id, body.dialogue_ids, task_id))
    return JSONResponse({"task_id": task_id, "status": "running", "episode_id": episode_id, "total": total})


async def _refresh_single_dialogue(project_id: str, episode_id: str, dlg: dict):
    """刷新单条对白状态的核心逻辑（从 api_refresh_dialogue 提取）。"""
    async def _replace_placeholder(placeholder, real_record):
        async with store.atomic_update() as data:
            for p in data["projects"]:
                if p["id"] == project_id:
                    for ep_in in p["episodes"]:
                        if ep_in["id"] == episode_id:
                            for d in ep_in["dialogues"]:
                                if d["id"] == dlg["id"]:
                                    d["audio_history"] = [
                                        a for a in d["audio_history"]
                                        if a.get("id") != placeholder["id"]
                                    ]
                                    d["audio_history"].append(real_record)
                                    d["current_audio_id"] = real_record["id"]
                                    d["status"] = "completed"
                                    return
                            break
                    break

    async def _try_download_audio(task_id, placeholder):
        try:
            result = await check_tts_status(task_id)
            if result["status"] in ("pending", "processing"):
                return False
            if result["status"] == "failed":
                async with store.atomic_update() as data:
                    for p in data["projects"]:
                        if p["id"] == project_id:
                            for ep_in in p["episodes"]:
                                if ep_in["id"] == episode_id:
                                    for d in ep_in["dialogues"]:
                                        if d["id"] == dlg["id"]:
                                            d["audio_history"] = [
                                                a for a in d["audio_history"]
                                                if a.get("id") != placeholder["id"]
                                            ]
                                            d["audio_history"].append({
                                                "id": f"failed_{uuid.uuid4().hex[:8]}",
                                                "url": "",
                                                "filename": "",
                                                "created_at": _now(),
                                                "status": "failed",
                                                "error": result["error"] or "TTS 任务失败",
                                            })
                                            d["status"] = "failed"
                                            return True
                                    break
                            break
                    return True
            client = get_client()
            loop = asyncio.get_event_loop()
            dl_result = await loop.run_in_executor(None, lambda: client.download(task_id))
            if not dl_result.ok:
                return False
            filename = f"{task_id}.wav"
            filepath = AUDIO_DIR / filename
            with open(filepath, "wb") as f:
                f.write(dl_result.data)
            real_id = f"audio_{uuid.uuid4().hex[:8]}"
            await _replace_placeholder(placeholder, {
                "id": real_id,
                "url": f"/static/audio/{filename}",
                "filename": filename,
                "created_at": _now(),
                "raw": True,
                "duration": _audio_duration(str(filepath)),
            })
            return True
        except Exception:
            return False

    # 1. 处理 generating 状态的占位记录
    for ah in dlg.get("audio_history", []):
        if ah.get("status") != "generating" or ah.get("url"):
            continue
        task_id = ah.get("task_id", "")
        if task_id:
            done = await _try_download_audio(task_id, ah)
            if done:
                return
        else:
            try:
                # 统一解析 TTS 参数（与单条/批量路径共用同一函数）
                # 注意：重试路径中 _data 已读取，直接用其中项目数据避免重复 IO
                _data = store._read()
                _proj = next((p for p in _data["projects"] if p["id"] == project_id), None)
                if not _proj:
                    continue
                tts_kwargs = _resolve_dialogue_tts_params(project_id, dlg, _proj)
                new_task_id = await submit_tts(**tts_kwargs)
                async with store.atomic_update() as data:
                    for p in data["projects"]:
                        if p["id"] == project_id:
                            for ep_in in p["episodes"]:
                                if ep_in["id"] == episode_id:
                                    for d in ep_in["dialogues"]:
                                        if d["id"] == dlg["id"]:
                                            for a in d["audio_history"]:
                                                if a.get("id") == ah["id"]:
                                                    a["task_id"] = new_task_id
                                                    a["interrupted"] = False
                                                    a["error"] = ""
                                                    break
                                            break
                                    break
                            break
            except Exception:
                pass

    # 2. 修复磁盘上已丢失的文件记录
    for ah in dlg.get("audio_history", []):
        fn = ah.get("filename", "")
        if not fn:
            continue
        fp = AUDIO_DIR / fn
        url = ah.get("url", "")
        if not fp.exists() and not url and ah.get("status") != "failed":
            ah["interrupted"] = True
            ah["error"] = "文件丢失，等待重试"

    async with store.atomic_update() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                for ep_in in p["episodes"]:
                    if ep_in["id"] == episode_id:
                        for d in ep_in["dialogues"]:
                            if d["id"] == dlg["id"]:
                                d["audio_history"] = dlg["audio_history"]
                                return
                        break
                break


@router.post("/projects/{project_id}/episodes/{episode_id}/generate-batch")
async def api_generate_batch_audio(project_id: str, episode_id: str, body: BatchAudioRequest):
    """批量提交所有对白的 TTS 任务，后台任务模式。"""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    total = len(body.dialogue_ids)

    from app.core.store import init_generation_task
    from app.core.dialogue_service import run_batch_generate
    task_id = init_generation_task(project_id, episode_id, "generate_batch", total=total)
    asyncio.create_task(run_batch_generate(project_id, episode_id, body.dialogue_ids, task_id))
    return JSONResponse({"task_id": task_id, "status": "running", "episode_id": episode_id, "total": total})


@router.delete("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/history")
async def api_clear_history(project_id: str, episode_id: str, dialogue_id: str):
    """Clear audio history for a dialogue."""
    dlg = clear_audio_history(project_id, episode_id, dialogue_id)
    if not dlg:
        raise HTTPException(404, "Dialogue not found")
    return dlg


@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/history/{audio_id}/activate")
async def api_set_current_audio(project_id: str, episode_id: str, dialogue_id: str, audio_id: str):
    """Set a specific audio as the current (active) audio for this dialogue."""
    dlg = set_current_audio(project_id, episode_id, dialogue_id, audio_id)
    if not dlg:
        raise HTTPException(404, "Dialogue or audio not found")
    return dlg


@router.delete("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/history/{audio_id}")
async def api_remove_audio(project_id: str, episode_id: str, dialogue_id: str, audio_id: str):
    """Remove a single audio entry from history."""
    dlg = remove_audio_from_history(project_id, episode_id, dialogue_id, audio_id)
    if not dlg:
        raise HTTPException(404, "Dialogue or audio not found")
    return dlg


# ── download endpoints ─────────────────────────────────

@router.get("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/download/{audio_id}")
async def api_download_audio(project_id: str, episode_id: str, dialogue_id: str, audio_id: str):
    """Download a specific audio file."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    for d in ep["dialogues"]:
        if d["id"] == dialogue_id:
            for ah in d.get("audio_history", []):
                if ah["id"] == audio_id:
                    filepath = AUDIO_DIR / ah.get("filename", "")
                    if filepath.exists():
                        return FileResponse(str(filepath), filename=ah.get("filename", "audio.wav"))
                    raise HTTPException(404, "Audio file not found on disk")
    raise HTTPException(404, "Audio not found")


@router.get("/projects/{project_id}/episodes/{episode_id}/download-all")
async def api_download_episode_audio(project_id: str, episode_id: str):
    """Download all current audio for an episode as a zip."""
    import zipfile
    import io

    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        sorted_dialogues = sorted(ep.get("dialogues", []), key=lambda x: x.get("order", 0))
        for d in sorted_dialogues:
            if d.get("current_audio_id"):
                for ah in d.get("audio_history", []):
                    if ah["id"] == d["current_audio_id"]:
                        fp = AUDIO_DIR / ah.get("filename", "")
                        if fp.exists():
                            order = d.get("order", 0)
                            char_name = d.get("character_name", "unknown")
                            dlg_id = d.get("id", "")
                            arcname = f"{order:03d}_{char_name}_{dlg_id[:6]}.wav"
                            zf.write(str(fp), arcname=arcname)

    # Check if any files were added
    buf.seek(0)
    with zipfile.ZipFile(buf, "r") as zf_check:
        if not zf_check.namelist():
            return JSONResponse(
                status_code=404,
                content={"error": "no_audio", "message": "No downloadable audio files in this episode"},
            )

    buf.seek(0)
    safe_title = "".join(c for c in ep["title"] if c.isalnum() or c in " _-")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={safe_title}_audio.zip"},
    )


# ── concatenate endpoint ────────────────────────────────

@router.get("/projects/{project_id}/episodes/{episode_id}/concatenate")
async def api_concatenate_episode_audio(
    project_id: str, episode_id: str,
    gap: float = 0.5, format: str = "wav", sample_rate: int = 24000,
):
    """Concatenate all current audio for an episode into a single file, with gaps between clips."""
    import numpy as np
    import time
    from app.core.timeline_audio import load_audio, save_audio

    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    # Collect dialogues with current audio, sorted by order
    dialogues_with_audio = []
    for d in sorted(ep.get("dialogues", []), key=lambda x: x.get("order", 0)):
        audio_id = d.get("current_audio_id")
        if not audio_id:
            continue
        audio_rec = None
        for ah in d.get("audio_history", []):
            if ah["id"] == audio_id:
                audio_rec = ah
                break
        if audio_rec and audio_rec.get("filename"):
            dialogues_with_audio.append(audio_rec)

    skipped = len(ep.get("dialogues", [])) - len(dialogues_with_audio)

    if not dialogues_with_audio:
        raise HTTPException(404, "No audio files found for this episode")

    # Load audio buffers
    audio_buffers = []
    for rec in dialogues_with_audio:
        try:
            audio, sr = load_audio(rec["filename"], target_sr=sample_rate)
            audio_buffers.append(audio)
        except Exception as e:
            skipped += 1
            import logging
            logging.warning(f"Failed to load audio {rec.get('filename', 'unknown')}: {e}")

    if not audio_buffers:
        raise HTTPException(404, "No audio files could be loaded")

    # Add silence gaps between clips
    gap_samples = int(gap * sample_rate)
    gap_buffer = np.zeros(gap_samples, dtype=np.float32)
    result_parts = []
    for i, buf in enumerate(audio_buffers):
        result_parts.append(buf)
        if i < len(audio_buffers) - 1:
            result_parts.append(gap_buffer)
    mixed = np.concatenate(result_parts)

    # Save
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_fn = f"concat_{episode_id[:8]}_{timestamp}.{fmt}"
    out_path = save_audio(mixed, out_fn, sample_rate)

    safe_title = "".join(c for c in ep["title"] if c.isalnum() or c in " _-")
    resp = FileResponse(str(out_path), filename=f"{safe_title}_concat.{fmt}", media_type="audio/wav")
    resp.headers["X-Skipped-Count"] = str(skipped)
    return resp


# ── refresh / fix endpoints ─────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/refresh")
async def api_refresh_dialogue(project_id: str, episode_id: str, dialogue_id: str):
    """Refresh dialogue status: check generating tasks and fix missing audio files."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    dlg = None
    for d in ep["dialogues"]:
        if d["id"] == dialogue_id:
            dlg = d
            break
    if not dlg:
        raise HTTPException(404, "Dialogue not found")

    await _refresh_single_dialogue(project_id, episode_id, dlg)
    return get_episode(project_id, episode_id)


# ── apply effects endpoints ────────────────────────────

@router.post("/projects/{project_id}/episodes/{episode_id}/dialogues/{dialogue_id}/apply-effects")
async def api_apply_effects(project_id: str, episode_id: str, dialogue_id: str):
    """对当前起效的原始音频应用角色音效链，生成新历史记录并自动起效。"""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    dlg = None
    for d in ep["dialogues"]:
        if d["id"] == dialogue_id:
            dlg = d
            break
    if not dlg:
        raise HTTPException(404, "Dialogue not found")

    # 找到当前起效的音频
    current_audio_id = dlg.get("current_audio_id")
    if not current_audio_id:
        raise HTTPException(400, "没有起效的音频，请先生成音频")

    current_ah = None
    for ah in dlg.get("audio_history", []):
        if ah["id"] == current_audio_id:
            current_ah = ah
            break
    if not current_ah:
        raise HTTPException(404, "当前起效的音频记录不存在")

    filename = current_ah.get("filename", "")
    if not filename:
        raise HTTPException(400, "当前音频没有文件记录")

    src_path = AUDIO_DIR / filename
    if not src_path.exists():
        raise HTTPException(404, "音频文件不存在于磁盘")

    # 获取角色音效链
    proj = get_project(project_id)
    char = None
    for c in proj["characters"]:
        if c["id"] == dlg.get("character_id"):
            char = c
            break

    effects = char.get("audio_effects", []) if char else []
    if not effects:
        raise HTTPException(400, "该角色没有配置音效，请先在角色面板添加音效")

    # 应用音效，生成新文件
    try:
        from app.core.audio_effects import apply_effects_to_file
        new_filename = f"fx_{uuid.uuid4().hex[:8]}.wav"
        new_filepath = AUDIO_DIR / new_filename
        apply_effects_to_file(str(src_path), str(new_filepath), effects)
    except Exception as e:
        raise HTTPException(500, f"音效处理失败: {e}")

    # 添加新历史记录并起效
    new_id = f"audio_{uuid.uuid4().hex[:8]}"
    audio_url = f"/static/audio/{new_filename}"
    async with store.atomic_update() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                for ep_in in p["episodes"]:
                    if ep_in["id"] == episode_id:
                        for d in ep_in["dialogues"]:
                            if d["id"] == dialogue_id:
                                d["audio_history"].append({
                                    "id": new_id,
                                    "url": audio_url,
                                    "filename": new_filename,
                                    "created_at": _now(),
                                    "raw": False,
                                    "duration": _audio_duration(str(new_filepath)),
                                })
                                d["current_audio_id"] = new_id
                                d["status"] = "completed"
                                return get_episode(project_id, episode_id)
                        break
                break

    raise HTTPException(500, "更新数据失败")


# ── import / export endpoints ──────────────────────────

class EpisodeImport(BaseModel):
    title: str
    dialogues: list[BatchDialogueCreate]

class ProjectImport(BaseModel):
    name: str
    characters: list[dict] = []
    episodes: list[EpisodeImport] = []


@router.get("/projects/{project_id}/episodes/{episode_id}/export")
async def api_export_episode(project_id: str, episode_id: str):
    """Export episode as JSON."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    return JSONResponse(ep)


@router.post("/projects/{project_id}/episodes/{episode_id}/import")
async def api_import_dialogues(project_id: str, episode_id: str, body: EpisodeImport):
    """Import dialogues into an episode from JSON."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")
    results = []
    for i, item in enumerate(body.dialogues):
        dlg = add_dialogue(project_id, episode_id, item.character_id, item.text, item.order or i, item.instruct)
        if dlg:
            results.append(dlg)
    return results


@router.get("/projects/{project_id}/export")
async def api_export_project(project_id: str):
    """Export entire project as JSON."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    return JSONResponse(proj)


@router.post("/projects/{project_id}/import")
async def api_import_project(project_id: str, body: ProjectImport):
    """Import data into a project (episodes + dialogues)."""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")
    results = []
    for ep_imp in body.episodes:
        new_ep = create_episode(project_id, ep_imp.title)
        if new_ep:
            for i, item in enumerate(ep_imp.dialogues):
                add_dialogue(project_id, new_ep["id"], item.character_id, item.text, item.order or i, item.instruct)
            results.append(new_ep["id"])
    return {"imported": len(results), "episode_ids": results}


# ── LLM generation endpoints ───────────────────────────

from app.core.llm import chat_json, get_llm_config
from app.core.task_manager import TaskManager


class EpisodeGenRequest(BaseModel):
    description: str = ""  # 故事描述 / 走向微调指令（可选，留空则基于前情自动续写）
    num_episodes: int = 3  # 生成几集
    extra: str = ""  # 额外要求（可选）


class DialogueGenRequest(BaseModel):
    instruction: str = ""  # 额外指令（可选）
    target_duration_min: int = 25  # 目标时长（分钟），默认 25
    narration_ratio: int = 50  # 旁白比例 0-100，默认 50
    style: str = ""  # 故事风格（可选）
    temperature: float = 0.7  # LLM 温度（默认 0.7）


# ── Regenerate outline from a specific episode ──────────

@router.post("/projects/{project_id}/regenerate-from/{episode_id}")
async def api_regenerate_from(project_id: str, episode_id: str, body: EpisodeGenRequest):
    """
    从指定集数开始重新生成大纲。
    - 保留指定集数（含）之前的所有剧集
    - 删除指定集数之后的所有剧集及其音频文件
    - 以已有剧集为上下文，重新生成 num_episodes 集新大纲
    """
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")


    # 找到指定集在列表中的索引
    ep_index = None
    for i, ep in enumerate(proj.get("episodes", [])):
        if ep["id"] == episode_id:
            ep_index = i
            break
    if ep_index is None:
        raise HTTPException(404, "Episode not found")

    llm_cfg = get_llm_config()
    if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
        raise HTTPException(400, "LLM 未配置")

    # 1. 删除指定集数之后的所有剧集及其音频文件
    episodes_after = proj["episodes"][ep_index + 1:]
    deleted_count = len(episodes_after)
    for ep_del in episodes_after:
        # 删除该集所有对白的音频文件
        for d in ep_del.get("dialogues", []):
            for ah in d.get("audio_history", []):
                fn = ah.get("filename", "")
                if fn:
                    fp = AUDIO_DIR / fn
                    if fp.exists():
                        os.remove(str(fp))
        # 从 store 删除
        delete_episode(project_id, ep_del["id"])

    # 2. 清除指定集数本身的音频（剧情走向变了，旧音频不再适用）
    keep_ep = get_episode(project_id, episode_id)
    if keep_ep:
        for d in keep_ep.get("dialogues", []):
            for ah in d.get("audio_history", []):
                fn = ah.get("filename", "")
                if fn:
                    fp = AUDIO_DIR / fn
                    if fp.exists():
                        os.remove(str(fp))
            clear_audio_history(project_id, episode_id, d["id"])

    # 3. 构建上下文：已有剧集摘要（含当前集）
    chars_info = _build_chars_info(proj)

    # 已有剧集摘要（含当前集及之前）
    existing_eps = []
    for i, ep in enumerate(proj.get("episodes", [])):
        if ep.get("summary"):
            existing_eps.append(f"第{i + 1}集《{ep['title']}》: {ep['summary']}")

    system_prompt = """你是一个专业的编剧助手，生成完整连贯的长篇故事大纲。

规则：
- 所有剧集构成完整故事弧线（铺垫→发展→高潮→结局）
- 每集摘要 150-250 字，承上启下，包含核心冲突、角色变化、情感基调、悬念
- 角色去留、生死、关系变化前后一致
- 标题只写纯标题，不要加"第X集"前缀

返回 JSON：{"story_arc": "一句话故事弧线", "episodes": [{"title": "纯标题，不含集数", "summary": "摘要（含角色去留变化）", "arc_phase": "铺垫|发展|高潮|结局|完整故事线"}]}"""

    # 主线从前情提要推断，description 作为可选的走向微调指令
    if body.description.strip():
        user_content = f"后续走向微调：{body.description}\n\n"
    else:
        user_content = ""
    if chars_info:
        user_content += f"已有角色：\n" + "\n".join(chars_info) + "\n\n"
    if existing_eps:
        user_content += f"前情提要（请在此基础上续写，保持故事连贯）：\n" + "\n".join(existing_eps) + "\n\n"
    if body.extra:
        user_content += f"额外要求：{body.extra}\n\n"
    if body.num_episodes == 1:
        user_content += f"请从下一集开始，生成 1 集大纲。这是唯一一集，需要包含完整故事线（起承转合），arc_phase 必须为「完整故事线」。故事主线不变，保持角色和设定一致。"
    else:
        user_content += f"请从下一集开始，生成 {body.num_episodes} 集大纲。故事主线不变，保持角色和设定一致。"

    try:
        result = await chat_json([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ], max_tokens=8000)
    except Exception as e:
        raise HTTPException(502, f"LLM 调用失败: {e}")

    # 4. 创建新大纲剧集（清理 LLM 标题中可能含有的"第X集"前缀）
    import re as _re
    episodes_data = result.get("episodes", [])
    created = []
    for ep_data in episodes_data:
        title = _re.sub(r'^第\s*\d+\s*集[《》]?\s*', '', ep_data.get("title", "未命名剧集")).strip() or "未命名剧集"
        summary = ep_data.get("summary", "")
        arc_phase = ep_data.get("arc_phase", "")
        # 单集强制使用"完整故事线"
        if body.num_episodes == 1:
            arc_phase = "完整故事线"
        full_summary = f"[{arc_phase}] {summary}" if arc_phase else summary
        ep = create_episode(project_id, title)
        if ep and full_summary:
            update_episode(project_id, ep["id"], summary=full_summary)
        if ep:
            created.append(ep["id"])

    return {
        "created": len(created),
        "episode_ids": created,
        "story_arc": result.get("story_arc", ""),
        "story_title": result.get("story_title", ""),
        "deleted": deleted_count,
    }


@router.post("/projects/{project_id}/generate-episodes")
async def api_generate_episodes(project_id: str, body: EpisodeGenRequest):
    """用 LLM 根据描述生成完整故事大纲。后台任务模式（F2+F3+F5）。"""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    llm_cfg = get_llm_config()
    if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
        raise HTTPException(400, "LLM 未配置")

    # F3: 单次锁定
    if not TaskManager.try_acquire(project_id, project_id, "outline"):
        raise HTTPException(409, "该项目正在生成大纲，请等待完成后再试")

    task_id = TaskManager.create(project_id, project_id, "outline")
    if not task_id:
        TaskManager.release(project_id, "outline")
        raise HTTPException(500, "创建任务失败")

    asyncio.create_task(_bg_generate_episodes(project_id, body, task_id))

    return JSONResponse({"task_id": task_id, "status": "running"})


async def _bg_generate_episodes(project_id: str, body: EpisodeGenRequest, task_id: str):
    """后台生成大纲（F5: 串行，F4: 超时）"""
    try:
        proj = get_project(project_id)
        chars_info = _build_chars_info(proj)

        existing_eps = []
        for ep in proj.get("episodes", []):
            if ep.get("summary"):
                existing_eps.append(f"第{proj['episodes'].index(ep) + 1}集《{ep['title']}》: {ep['summary']}")

        system_prompt = """你是一个专业的编剧助手，生成完整连贯的长篇故事大纲。

规则：
- 所有剧集构成完整故事弧线（铺垫→发展→高潮→结局）
- 每集摘要 150-250 字，承上启下，包含核心冲突、角色变化、情感基调、悬念
- 角色去留、生死、关系变化前后一致
- 标题只写纯标题，不要加"第X集"前缀

返回 JSON：{"story_title": "故事标题（2-6个字，精炼有吸引力）", "story_arc": "一句话故事弧线", "episodes": [{"title": "纯标题，不含集数", "summary": "摘要（含角色去留变化）", "arc_phase": "铺垫|发展|高潮|结局|完整故事线"}]}"""

        user_content = f"故事描述：{body.description}\n\n"
        if chars_info:
            user_content += f"已有角色：\n" + "\n".join(chars_info) + "\n\n"
        if existing_eps:
            user_content += f"已有剧集（续写时请保持连贯）：\n" + "\n".join(existing_eps) + "\n\n"
        if body.extra:
            user_content += f"额外要求：{body.extra}\n\n"
        if body.num_episodes == 1:
            user_content += f"生成 1 集大纲，这是唯一一集，需要包含完整故事线（起承转合），arc_phase 必须为「完整故事线」。"
        else:
            user_content += f"生成 {body.num_episodes} 集大纲。"

        TaskManager.update(project_id, task_id, status="running:generating")

        result = await asyncio.wait_for(
            chat_json([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ], max_tokens=8000),
            timeout=300
        )

        import re as _re
        episodes_data = result.get("episodes", [])
        created = []
        for ep_data in episodes_data:
            title = _re.sub(r'^第\s*\d+\s*集[《》]?\s*', '', ep_data.get("title", "未命名剧集")).strip() or "未命名剧集"
            summary = ep_data.get("summary", "")
            arc_phase = ep_data.get("arc_phase", "")
            if body.num_episodes == 1:
                arc_phase = "完整故事线"
            full_summary = f"[{arc_phase}] {summary}" if arc_phase else summary
            ep = create_episode(project_id, title)
            if ep and full_summary:
                update_episode(project_id, ep["id"], summary=full_summary)
            if ep:
                created.append(ep["id"])

        TaskManager.update(project_id, task_id, status="complete",
            current=len(created), total=len(episodes_data),
            result={"created": len(created), "episode_ids": created})
    except asyncio.TimeoutError:
        TaskManager.update(project_id, task_id, status="timeout", error="大纲生成超时（5分钟）")
    except Exception as e:
        TaskManager.update(project_id, task_id, status="error", error=str(e))
    finally:
        TaskManager.release(project_id, "outline")


@router.post("/projects/{project_id}/episodes/{episode_id}/generate-dialogues")
async def api_generate_dialogues(project_id: str, episode_id: str, body: DialogueGenRequest):
    """用 LLM 根据剧集摘要生成完整故事文本（方案B-2），解析后入库。
    改为后台任务模式，立即返回 task_id，前端轮询 /generation-status 获取进度。"""
    from app.core.store import init_generation_task
    from app.core.dialogue_service import run_dialogue_generation

    # F3: 单次锁定
    if not TaskManager.try_acquire(project_id, episode_id, "dialogues"):
        raise HTTPException(409, "该剧集正在生成对白，请等待完成后再试")

    # 2. 初始化任务记录
    task_id = init_generation_task(project_id, episode_id, "dialogue_generation")

    # 3. 在锁保护下启动后台任务
    async def _locked_generation():
        async with _gen_locks.get(project_id, asyncio.Lock()):
            await run_dialogue_generation(project_id, episode_id, body, task_id)
            TaskManager.release(project_id, episode_id, "dialogues")

    asyncio.create_task(_locked_generation())

    # 4. 立即返回
    return JSONResponse({
        "task_id": task_id,
        "status": "running",
        "episode_id": episode_id,
    })

@router.get("/projects/{project_id}/generation-status")
async def api_get_generation_status(project_id: str, episode_id: str = None):
    """查询当前生成任务状态。前端重连后调用此接口获取进度。"""
    from app.core.store import get_generation_task
    task = get_generation_task(project_id, episode_id=episode_id)
    if not task:
        return JSONResponse({"status": "idle"})
    return JSONResponse(task)

@router.post("/projects/{project_id}/episodes/{episode_id}/generate-next")
async def api_generate_next_episode(project_id: str, episode_id: str):
    """根据当前剧集摘要，生成下一集的内容（摘要+对白）。后台任务模式。"""
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    ep = get_episode(project_id, episode_id)
    if not ep:
        raise HTTPException(404, "Episode not found")

    llm_cfg = get_llm_config()
    if not llm_cfg.get("base_url") or not llm_cfg.get("api_key"):
        raise HTTPException(400, "LLM 未配置")

    # F3: 单次锁定
    if not TaskManager.try_acquire(project_id, episode_id, "continuation"):
        raise HTTPException(409, "该剧集正在续写中，请等待完成后再试")

    task_id = TaskManager.create(project_id, episode_id, "continuation")
    if not task_id:
        TaskManager.release(project_id, episode_id, "continuation")
        raise HTTPException(500, "创建任务失败")

    asyncio.create_task(_bg_generate_next(project_id, episode_id, task_id))
    return JSONResponse({"task_id": task_id, "status": "running"})


async def _bg_generate_next(project_id: str, episode_id: str, task_id: str):
    """后台续写下一集"""
    try:
        proj = get_project(project_id)
        ep = get_episode(project_id, episode_id)

        current_summary = ep.get("summary", "")
        current_dialogues = []
        for d in ep.get("dialogues", []):
            if d.get("text"):
                current_dialogues.append(f"{d.get('character_name', '未知')}: {d['text']}")

        prev_summaries = []
        for prev_ep in proj.get("episodes", []):
            if prev_ep["id"] == episode_id:
                break
            if prev_ep.get("summary"):
                prev_summaries.append(f"《{prev_ep['title']}》: {prev_ep['summary']}")

        chars_info = _build_chars_info(proj)

        system_prompt = """你是一个专业的编剧助手，负责生成下一集内容。
根据前情提要和当前剧情，生成下一集的标题、摘要。
返回 JSON 格式：{"title": "下一集标题", "summary": "下一集摘要（100字以内）"}"""

        user_content = f"当前剧集《{ep['title']}》摘要：{current_summary}\n\n"
        if current_dialogues:
            user_content += f"当前剧集对白节选：\n" + "\n".join(current_dialogues[:5]) + "\n\n"
        if prev_summaries:
            user_content += f"前情提要：\n" + "\n".join(prev_summaries) + "\n\n"
        if chars_info:
            user_content += f"已有角色：\n" + "\n".join(chars_info) + "\n\n"
        user_content += "请生成下一集的标题和摘要。"

        TaskManager.update(project_id, task_id, status="running:generating")

        result = await asyncio.wait_for(
            chat_json([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]),
            timeout=300
        )

        title = result.get("title", "下一集")
        summary = result.get("summary", "")
        new_ep = create_episode(project_id, title)
        if new_ep and summary:
            update_episode(project_id, new_ep["id"], summary=summary)

        TaskManager.update(project_id, task_id, status="complete",
            result={"episode_id": new_ep["id"] if new_ep else None, "title": title, "summary": summary})
    except asyncio.TimeoutError:
        TaskManager.update(project_id, task_id, status="timeout", error="续写生成超时（5分钟）")
    except Exception as e:
        TaskManager.update(project_id, task_id, status="error", error=str(e))
    finally:
        TaskManager.release(project_id, episode_id, "continuation")


# ── Batch character replacement ─────────────────────────

class BatchReplaceCharRequest(BaseModel):
    """按章节批量换角：将指定章节列表中某角色替换为另一角色。"""
    old_name: str       # 要被替换的角色名（如"小明少年"）
    new_name: str       # 替换后的角色名（如"小明青年"）
    episode_ids: list[str]  # 要操作的章节 ID 列表（空列表 = 所有章节）
    create_if_missing: bool = True  # 如果 new_name 角色不存在，是否自动创建


@router.post("/projects/{project_id}/batch-replace-character")
async def api_batch_replace_character(project_id: str, body: BatchReplaceCharRequest):
    """
    按章节批量换角。
    - episode_ids 为空时操作所有章节
    - new_name 角色不存在时自动创建（复用 old_name 的音色）
    - 返回替换了多少条对白、涉及多少章节
    """
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    old_name = body.old_name.strip()
    new_name = body.new_name.strip()

    if not old_name or not new_name:
        raise HTTPException(400, "角色名不能为空")
    if old_name == new_name:
        raise HTTPException(400, "新旧角色名相同，无需替换")
    if old_name in ("旁白", "场景"):
        raise HTTPException(400, "不能替换旁白或场景")

    # 确定要操作的章节范围
    target_ep_ids = set(body.episode_ids) if body.episode_ids else None

    # 查找 new_name 角色
    new_char = None
    for c in proj.get("characters", []):
        if c["name"].strip() == new_name:
            new_char = c
            break

    # 找不到就创建
    if not new_char and body.create_if_missing:
        from app.core.store import add_character
        old_voice = None
        for c in proj.get("characters", []):
            if c["name"].strip() == old_name:
                old_voice = c.get("voice_id", "")
                break
        voice_id = old_voice or ""
        new_char = add_character(project_id, new_name, voice_id, description=f"由「{old_name}」换角创建")
        if new_char:
            proj["characters"].append(new_char)

    if not new_char:
        raise HTTPException(404, f"目标角色「{new_name}」不存在")

    new_char_id = new_char["id"]

    # 找到 old_name 角色的 id
    old_char_id = None
    for c in proj.get("characters", []):
        if c["name"].strip() == old_name:
            old_char_id = c["id"]
            break

    # 遍历目标章节的对白，替换角色
    replaced = 0
    affected_eps: set[str] = set()
    for ep in proj.get("episodes", []):
        if target_ep_ids is not None and ep["id"] not in target_ep_ids:
            ep_in_scope = False
        else:
            ep_in_scope = True
        if not ep_in_scope:
            continue
        for dlg in ep.get("dialogues", []):
            match = False
            if old_char_id and dlg.get("character_id") == old_char_id:
                match = True
            elif dlg.get("character_name", "").strip() == old_name:
                match = True
            if match:
                dlg["character_id"] = new_char_id
                dlg["character_name"] = new_name
                replaced += 1
                affected_eps.add(ep["id"])

    # 持久化
    async with store.atomic_update() as data:
        for p in data["projects"]:
            if p["id"] == project_id:
                p["episodes"] = proj["episodes"]
                p["characters"] = proj["characters"]
                break

    return {
        "replaced": replaced,
        "affected_episodes": len(affected_eps),
        "old_name": old_name,
        "new_name": new_name,
    }
