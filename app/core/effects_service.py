"""角色音效批量应用服务（单任务模式）

Refs #108 — 替换旧 per-dialogue 异步任务模式为单任务模式。
设计思路：一个批量应用操作为一个任务记录，内置逐条对白处理循环，
进度通过 TaskManager.update(current=i) 更新。

设计原因：
- 旧模式为每一条对白创建独立后台任务 → 任务面板被淹死
- 用户只关心「角色 X 的音效是否已全部应用完成」
- 参照剧集批量生成声音（api_generate_batch_audio）的架构模式
"""

import asyncio
import uuid as _uuid
from pathlib import Path
from logging import getLogger

from app.core.task_manager import TaskManager
from app.core.audio_effects import apply_effects_to_file, compute_effects_checksum

logger = getLogger("tts-studio")

# ── 共享引用（由 main.py 初始化）─
DATA_DIR: Path | None = None
AUDIO_DIR: Path | None = None
_store = None


def init(dir_path: Path, store_module):
    """由 main.py 在启动时调用，注入目录和 store 引用。"""
    global DATA_DIR, AUDIO_DIR, _store
    DATA_DIR = dir_path
    AUDIO_DIR = dir_path / "audio"
    _store = store_module


# #108: 从 main.py L115-L166 迁移而来，逻辑一字不动
def decide_dialogue_effect(dialogue: dict, checksum: str) -> dict:
    """对单个对白执行「定位→对比→决策」。

    对应 Issue: #103 / #108
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
            raw_id = current_ah.get("effects_source_id")
            return {"action": "process", "mode": "replace", "raw_audio_id": raw_id}
    else:
        # 当前是原音（effects_source_id is None）
        existing_fx = next(
            (ah for ah in audio_history
             if ah.get("effects_source_id") == current_audio_id
             and ah.get("effects_checksum") is not None),
            None
        )
        if existing_fx and existing_fx.get("effects_checksum") == checksum:
            return {"action": "skip"}
        else:
            return {"action": "process", "mode": "add", "raw_audio_id": current_audio_id}


async def bg_apply_character_effects(
    project_id: str,
    char_id: str,
    checksum: str,
    task_id: str,
):
    """后台执行：遍历项目所有剧集，对指定角色的对白应用音效。

    Refs #108 — 单任务模式，内部逐条处理并更新进度。

    Args:
        project_id: 项目 ID
        char_id: 角色 ID
        checksum: 音效链校验码
        task_id: 任务 ID（由 init_generation_task 创建）
    """
    from app.core.store import get_project

    try:
        project = get_project(project_id)
        if not project:
            raise ValueError("项目不存在")

        # 从项目数据中获取角色音效链
        char = None
        for c in project.get("characters", []):
            if c["id"] == char_id:
                char = c
                break
        if not char:
            raise ValueError("角色不存在")

        effects_chain = char.get("audio_effects", [])
        if not effects_chain:
            raise ValueError("该角色没有配置音效")

        # 扫描所有剧集的所有对白
        processed = 0
        total = 0
        for ep_in in project.get("episodes", []):
            for d in ep_in.get("dialogues", []):
                if d.get("character_id") != char_id:
                    continue
                total += 1

        # 逐条处理
        for ep_in in project.get("episodes", []):
            episode_id = ep_in["id"]
            for d in ep_in.get("dialogues", []):
                if d.get("character_id") != char_id:
                    continue

                dialogue_id = d["id"]
                decision = decide_dialogue_effect(d, checksum)

                if decision["action"] == "skip":
                    processed += 1
                    TaskManager.update(project_id, task_id, current=processed)
                    continue

                # 执行音频处理（复用旧 _execute_apply_effect_task 逻辑）
                try:
                    await _process_single_dialogue(
                        project_id, episode_id, dialogue_id,
                        decision, effects_chain, checksum,
                    )
                except Exception as e:
                    logger.error("音效处理失败 [%s/%s]: %s", episode_id, dialogue_id, e)
                    # 单条失败不阻塞整体，标记后继续

                processed += 1
                TaskManager.update(project_id, task_id, current=processed)

        TaskManager.update(project_id, task_id, status="complete", current=total)

    except Exception as e:
        logger.error("批量音效应用失败 [%s]: %s", task_id, e)
        TaskManager.update(project_id, task_id, status="error", error=str(e))
    finally:
        TaskManager.release(project_id, "apply_effects")


async def _process_single_dialogue(
    project_id: str,
    episode_id: str,
    dialogue_id: str,
    decision: dict,
    effects_chain: list,
    checksum: str,
):
    """处理单条对白的音效应用（add/replace/create 模式）。

    Refs #108 — 从旧 _execute_apply_effect_task (main.py L267-L402) 提取核心逻辑。
    """
    from app.core.audio_effects import apply_effects_to_file
    from app.api.episodes import _audio_duration

    project = _store.get_project(project_id)
    if not project:
        raise ValueError("项目不存在")

    episode = next(
        (ep for ep in project.get("episodes", []) if ep["id"] == episode_id),
        None,
    )
    if not episode:
        raise ValueError("剧集不存在")

    dialogue = next(
        (d for d in episode.get("dialogues", []) if d["id"] == dialogue_id),
        None,
    )
    if not dialogue:
        raise ValueError("对白不存在")

    mode = decision["mode"]
    raw_audio_id = decision["raw_audio_id"]

    # create 模式 — 无音频时跳过；有音频时降级为 add
    if mode == "create":
        if not dialogue.get("current_audio_id"):
            return  # 无音频，跳过
        mode = "add"
        raw_audio_id = dialogue["current_audio_id"]

    # 定位原音文件
    audio_history = dialogue.get("audio_history", [])
    src_ah = next(
        (ah for ah in audio_history if ah["id"] == raw_audio_id),
        None,
    )
    if not src_ah:
        raise ValueError("原音记录不存在")
    src_filename = src_ah.get("filename", "")
    if not src_filename:
        raise ValueError("原音文件名缺失")

    src_path = AUDIO_DIR / src_filename
    if not src_path.exists():
        raise ValueError(f"原音文件不存在: {src_path}")

    # replace 模式：查找旧效果音记录并删除旧文件
    old_fx_id = None
    if mode == "replace":
        old_fx = next(
            (ah for ah in audio_history
             if ah.get("effects_source_id") == raw_audio_id
             and ah.get("effects_checksum") is not None),
            None,
        )
        if old_fx and old_fx.get("filename"):
            old_file = AUDIO_DIR / old_fx["filename"]
            if old_file.exists():
                old_file.unlink()
        if old_fx:
            old_fx_id = old_fx["id"]

    # 生成新音频文件（在线程池中执行 CPU 密集处理）
    new_filename = f"fx_{_uuid.uuid4().hex[:8]}.wav"
    new_filepath = AUDIO_DIR / new_filename
    await asyncio.to_thread(
        apply_effects_to_file, str(src_path), str(new_filepath), effects_chain,
    )
    new_duration = _audio_duration(str(new_filepath))

    # atomic_update 内仅做数据写入
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
