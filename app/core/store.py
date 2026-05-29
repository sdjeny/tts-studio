"""JSON file-based persistence layer."""
import json
import uuid
import time
import os
import copy
import asyncio
import threading
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager

import yaml as _yaml

_CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.yaml"


def _load_tts_defaults() -> dict:
    """从 config.yaml 读取 tts.defaults，fallback 到保守默认值。"""
    _CONSERVATIVE = {
        "temperature": 0.05,
        "do_sample": False,
        "top_k": 5,
        "top_p": 0.3,
        "repetition_penalty": 1.1,
        "voice_id": "",
    }
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _yaml.safe_load(f) or {}
            tts_defaults = cfg.get("tts", {}).get("defaults")
            if tts_defaults and isinstance(tts_defaults, dict):
                # 确保所有必要字段存在，缺失的用保守值补充
                merged = {**_CONSERVATIVE, **tts_defaults}
                return merged
    except Exception:
        pass
    return _CONSERVATIVE


def _load_gen_defaults() -> dict:
    """从 config.yaml 读取 gen.defaults，fallback 到保守默认值。"""
    _CONSERVATIVE = {
        "num_episodes": 3,
        "target_duration_min": 25,
        "narration_ratio": 50,
    }
    try:
        if _CONFIG_PATH.exists():
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = _yaml.safe_load(f) or {}
            gen_defaults = cfg.get("gen", {}).get("defaults")
            if gen_defaults and isinstance(gen_defaults, dict):
                merged = {**_CONSERVATIVE, **gen_defaults}
                return merged
    except Exception:
        pass
    return _CONSERVATIVE

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_FILE = DATA_DIR / "studio.json"

PROJECTS_DIR = DATA_DIR / "projects"
INDEX_FILE = DATA_DIR / "projects_index.json"
BAK_FILE = DATA_DIR / "studio.json.bak"

def _project_path(project_id: str) -> Path:
    return PROJECTS_DIR / f"{project_id}.json"

# Module-level write lock for read-modify-write atomicity
_store_lock = asyncio.Lock()

_project_locks: dict[str, threading.Lock] = {}
_index_lock = threading.Lock()

def _get_project_lock(project_id: str) -> threading.Lock:
    if project_id not in _project_locks:
        _project_locks[project_id] = threading.Lock()
    return _project_locks[project_id]


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def _read_project(project_id: str) -> dict | None:
    """读取单个项目文件，不存在返回None"""
    path = _project_path(project_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_project(project_id: str, data: dict) -> None:
    """原子写入单个项目文件"""
    path = _project_path(project_id)
    tmp = str(path) + ".tmp"
    with _get_project_lock(project_id):
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(path))


def _read_index() -> dict:
    """读取索引，不存在返回默认"""
    if not INDEX_FILE.exists():
        return {"version": 1, "projects": []}
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_index(data: dict) -> None:
    """原子写入索引"""
    tmp = str(INDEX_FILE) + ".tmp"
    with _index_lock:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, str(INDEX_FILE))


def _index_add_project(project_id: str, name: str, updated_at: str) -> None:
    idx = _read_index()
    idx["projects"].append({"id": project_id, "name": name, "updated_at": updated_at, "characters_count": 0, "episodes_count": 0})
    _write_index(idx)


def _index_remove_project(project_id: str) -> None:
    idx = _read_index()
    idx["projects"] = [p for p in idx["projects"] if p["id"] != project_id]
    _write_index(idx)


def _index_update_project(project_id: str, name: str | None = None, updated_at: str | None = None,
                          characters_count: int | None = None, episodes_count: int | None = None) -> None:
    idx = _read_index()
    for p in idx["projects"]:
        if p["id"] == project_id:
            if name is not None: p["name"] = name
            if updated_at is not None: p["updated_at"] = updated_at
            if characters_count is not None: p["characters_count"] = characters_count
            if episodes_count is not None: p["episodes_count"] = episodes_count
            break
    _write_index(idx)


def _read() -> dict:
    """兼容旧调用方：从所有项目文件懒加载"""
    _ensure_data_dir()
    projects = []
    for pf in sorted(PROJECTS_DIR.glob("*.json")):
        with open(pf, "r", encoding="utf-8") as f:
            projects.append(json.load(f))
    return {"projects": projects}


def _write(data: dict):
    """兼容旧调用方：将数据分发到各项目文件"""
    for p in data.get("projects", []):
        _write_project(p["id"], p)

@asynccontextmanager
async def atomic_update():
    """
    Atomic update context manager for read-modify-write operations.

    Usage:
        async with atomic_update() as data:
            # modify data (deep copy from _read())
            ...
        # auto _write(data) on success
    """
    async with _store_lock:
        data = _read()
        try:
            yield data
        except Exception:
            raise
        else:
            _write(data)


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ─── Projects ────────────────────────────────────────────────

def list_projects() -> list[dict]:
    _ensure_data_dir()
    idx = _read_index()
    projects = idx.get("projects", [])
    # 兼容旧索引：缺 counts 的从项目文件补一次
    dirty = False
    for entry in projects:
        if "characters_count" not in entry:
            p = _read_project(entry["id"])
            if p is None:
                continue
            entry["characters_count"] = len(p.get("characters", []))
            entry["episodes_count"] = len(p.get("episodes", []))
            entry["updated_at"] = entry.get("updated_at") or p.get("created_at", "")
            if not p.get("tts_defaults"):
                p["tts_defaults"] = _load_tts_defaults()
                _write_project(entry["id"], p)
            dirty = True

        # 项目文件字段 backfill：独立检查，不依赖索引字段存在性
        p = _read_project(entry["id"])
        if p is None:
            continue
        if not p.get("gen_defaults"):
            p["gen_defaults"] = _load_gen_defaults()
            _write_project(entry["id"], p)
            dirty = True
        if not p.get("story_settings"):
            p["story_settings"] = {"description": "", "extra": "", "story_arc": ""}
            _write_project(entry["id"], p)
            dirty = True
    if dirty:
        _write_index(idx)
    # 补充 characters/episodes 数组字段供前端消费（索引只存 count，前端 .length 需要数组）
    for entry in projects:
        p = _read_project(entry["id"])
        if p is None:
            continue
        entry["characters"] = p.get("characters", [])
        entry["gen_defaults"] = p.get("gen_defaults", {})
        entry["story_settings"] = p.get("story_settings", {})
        entry["episodes"] = p.get("episodes", [])
        entry["created_at"] = p.get("created_at", "")
        entry["tts_defaults"] = p.get("tts_defaults", {})
    return sorted(projects, key=lambda p: p.get("updated_at", ""), reverse=True)


def get_project(project_id: str) -> dict | None:
    return _read_project(project_id)


def create_project(name: str) -> dict:
    _ensure_data_dir()
    now = _now()
    pid = _uid()
    project = {
        "id": pid,
        "name": name,
        "created_at": now,
        "updated_at": now,
        "characters": [],
        "episodes": [],
        # ── 项目级 TTS 默认参数 ────────────────────────────────
        # 当对白生成音频时未显式指定采样参数，则使用此处的值。
        # 保守默认值旨在最小化不同句子间的声音波动。
        "tts_defaults": _load_tts_defaults(),
        # ── 项目级生成默认值 ──────────────────────────────────
        # 控制生成剧集数量、目标时长、旁白比例等。
        "gen_defaults": _load_gen_defaults(),
        # ── 故事设定 ─────────────────────────────────────────
        "story_settings": {
            "description": "",
            "extra": "",
            "story_arc": "",
        },
    }
    _write_project(pid, project)
    _index_add_project(pid, name, now)
    return project


def update_project(project_id: str, name: str | None = None, **extra) -> dict | None:
    """更新项目字段。name 之外的字段（如 tts_defaults）通过 **extra 传入。"""
    p = _read_project(project_id)
    if p is None:
        return None
    name_changed = False
    if name is not None:
        p["name"] = name
        name_changed = True
    if extra:
        # 深度合并：对于嵌套 dict（如 tts_defaults），逐字段更新而非整体替换
        for k, v in extra.items():
            if isinstance(v, dict) and isinstance(p.get(k), dict):
                p[k].update(v)
            else:
                p[k] = v
    _write_project(project_id, p)
    if name_changed:
        _index_update_project(project_id, name=name)
    return p


def touch_project(project_id: str) -> None:
    """更新项目的 updated_at 时间戳。"""
    p = _read_project(project_id)
    if p is None:
        return
    now = _now()
    p["updated_at"] = now
    _write_project(project_id, p)
    _index_update_project(project_id, updated_at=now)


def delete_project(project_id: str) -> bool:
    p = _read_project(project_id)
    if p is None:
        return False
    # 删除关联的音频文件
    audio_dir = DATA_DIR / "audio"
    deleted_files = 0
    for ep in p.get("episodes", []):
        for dlg in ep.get("dialogues", []):
            for ah in dlg.get("audio_history", []):
                fn = ah.get("filename", "")
                if fn:
                    fp = audio_dir / fn
                    try:
                        if fp.exists():
                            os.remove(str(fp))
                            deleted_files += 1
                    except OSError:
                        pass
    # 删除项目文件
    path = _project_path(project_id)
    try:
        if path.exists():
            os.remove(str(path))
    except OSError:
        pass
    _index_remove_project(project_id)
    return True


# ─── Characters ──────────────────────────────────────────────

def project_characters(project_id: str) -> list[dict]:
    p = get_project(project_id)
    return p["characters"] if p else []


def add_character(project_id: str, name: str, voice_id: str, speed: float = 1.0,
                  pitch: float = 1.0, description: str = "",
                  audio_effects: list | None = None, **extra) -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    char = {
        "id": _uid(),
        "name": name,
        "voice_id": voice_id,
        "speed": speed,
        "pitch": pitch,
        "description": description,
        "audio_effects": audio_effects or [],
        "created_at": _now(),
    }
    char.update(extra)
    project["characters"].append(char)
    _write_project(project_id, project)
    _index_update_project(project_id, characters_count=len(project["characters"]))
    return char


def update_character(project_id: str, char_id: str, **fields) -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    for c in project["characters"]:
        if c["id"] == char_id:
            c.update(fields)
            _write_project(project_id, project)
            return c
    return None


def delete_character(project_id: str, char_id: str) -> bool:
    project = _read_project(project_id)
    if project is None:
        return False
    before = len(project["characters"])
    project["characters"] = [c for c in project["characters"] if c["id"] != char_id]
    if len(project["characters"]) < before:
        _write_project(project_id, project)
        _index_update_project(project_id, characters_count=len(project["characters"]))
        return True
    return False


# ─── Episodes ────────────────────────────────────────────────

def project_episodes(project_id: str) -> list[dict]:
    project = _read_project(project_id)
    if not project:
        return []
    # 数据迁移：旧 episode 补充 raw_text 字段
    dirty = False
    for ep in project["episodes"]:
        if "raw_text" not in ep:
            ep["raw_text"] = ""
            dirty = True
    if dirty:
        _write_project(project_id, project)
    return project["episodes"]


def get_episode(project_id: str, episode_id: str) -> dict | None:
    project = _read_project(project_id)
    if not project:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            # 数据迁移：旧 episode 补充 raw_text 字段
            if "raw_text" not in ep:
                ep["raw_text"] = ""
                _write_project(project_id, project)
            return ep
    return None


def create_episode(project_id: str, title: str, raw_text: str = "") -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    ep = {
        "id": _uid(),
        "title": title,
        "summary": "",
        "style_enabled": False,  # 剧集默认关闭风格
        "created_at": _now(),
        "dialogues": [],
        "raw_text": raw_text,
    }
    project["episodes"].append(ep)
    _write_project(project_id, project)
    _index_update_project(project_id, episodes_count=len(project["episodes"]))
    return ep


def update_episode(project_id: str, episode_id: str, **fields) -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            ep.update(fields)
            _write_project(project_id, project)
            return ep
    return None


def delete_episode(project_id: str, episode_id: str) -> bool:
    project = _read_project(project_id)
    if project is None:
        return False
    before = len(project["episodes"])
    project["episodes"] = [ep for ep in project["episodes"] if ep["id"] != episode_id]
    if len(project["episodes"]) < before:
        _write_project(project_id, project)
        _index_update_project(project_id, episodes_count=len(project["episodes"]))
        return True
    return False


# ─── Dialogues ───────────────────────────────────────────────

def episode_dialogues(project_id: str, episode_id: str) -> list[dict]:
    ep = get_episode(project_id, episode_id)
    return ep["dialogues"] if ep else []


def add_dialogue(project_id: str, episode_id: str, character_id: str,
                 text: str, order: int = 0, instruct: str = "") -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            # resolve character name（仅从真实角色查找）
            char_name = ""
            for c in project["characters"]:
                if c["id"] == character_id:
                    char_name = c["name"]
                    break
            if not char_name:
                char_id_display = character_id[:8] if character_id else "(空)"
                char_name = f"⚠ 角色异常({char_id_display})"
            dlg = {
                "id": _uid(),
                "character_id": character_id,
                "character_name": char_name,
                "text": text,
                "summary": "",
                "instruct": instruct,
                "style_enabled": False,  # True=角色风格+场景情绪, False=仅角色风格（默认关闭）
                "order": order,
                "status": "pending",  # pending | generating | completed | failed
                "audio_history": [],   # [{id, url, filename, created_at}]
                "current_audio_id": None,
                "created_at": _now(),
            }
            ep["dialogues"].append(dlg)
            _write_project(project_id, project)
            return dlg
    return None


def update_dialogue(project_id: str, episode_id: str, dialogue_id: str, **fields) -> dict | None:
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    dlg.update(fields)
                    # 如果更新了 character_id，自动同步 character_name
                    if "character_id" in fields:
                        cid = fields["character_id"]
                        char_name = ""
                        for c in project["characters"]:
                            if c["id"] == cid:
                                char_name = c["name"]
                                break
                        dlg["character_name"] = char_name or f"⚠ 角色异常({cid[:8]})"
                    _write_project(project_id, project)
                    return dlg
    return None

# Helper: update only status
def update_dialogue_status(project_id: str, episode_id: str, dialogue_id: str,
                           status: str) -> dict | None:
    return update_dialogue(project_id, episode_id, dialogue_id, status=status)


def delete_dialogue(project_id: str, episode_id: str, dialogue_id: str) -> bool:
    project = _read_project(project_id)
    if project is None:
        return False
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            before = len(ep["dialogues"])
            ep["dialogues"] = [d for d in ep["dialogues"] if d["id"] != dialogue_id]
            if len(ep["dialogues"]) < before:
                _write_project(project_id, project)
                return True
    return False


def insert_dialogue_after(project_id: str, episode_id: str, after_dialogue_id: str,
                         character_id: str = "", text: str = "", instruct: str = "") -> tuple[dict | None, int]:
    """在指定对白之后插入一条新对白。返回 (新对白 dict, affected 数量)，或 (None, 0)（找不到目标）。"""
    project = _read_project(project_id)
    if project is None:
        return None, 0
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            dialogues = ep["dialogues"]
            idx = None
            for i, d in enumerate(dialogues):
                if d["id"] == after_dialogue_id:
                    idx = i
                    break
            if idx is None:
                return None, 0
            target = dialogues[idx]
            new_order = target["order"] + 1
            for j in range(idx + 1, len(dialogues)):
                dialogues[j]["order"] += 1
            affected = len(dialogues) - idx - 1
            if not character_id:
                character_id = target["character_id"]
            # 解析 character_name，角色不存在时 fallback 到第一个角色
            char_name = ""
            for c in project["characters"]:
                if c["id"] == character_id:
                    char_name = c["name"]
                    break
            if not char_name and project["characters"]:
                char_name = project["characters"][0]["name"]
                character_id = project["characters"][0]["id"]
            if not char_name:
                char_id_display = character_id[:8] if character_id else "(空)"
                char_name = f"⚠ 角色异常({char_id_display})"
            new_dlg = {
                "id": _uid(),
                "character_id": character_id,
                "character_name": char_name,
                "text": text,
                "summary": "",
                "instruct": instruct,
                "style_enabled": False,
                "order": new_order,
                "status": "pending",
                "audio_history": [],
                "current_audio_id": None,
                "created_at": _now(),
            }
            dialogues.insert(idx + 1, new_dlg)
            _write_project(project_id, project)
            return new_dlg, affected
    return None, 0


def reorder_episode_dialogues(project_id: str, episode_id: str) -> int:
    """重建整个 episode 的 order 连续性。返回修复的重复数。"""
    project = _read_project(project_id)
    if project is None:
        return 0
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            dialogues = ep["dialogues"]
            # 按当前 order 排序，然后重建连续 order
            dialogues.sort(key=lambda d: (d["order"], d.get("created_at", "")))
            for i, d in enumerate(dialogues):
                d["order"] = i
            _write_project(project_id, project)
            return len(dialogues)
    return 0


def delete_dialogue_and_audio_files(project_id: str, episode_id: str, dialogue_id: str) -> tuple[bool, int]:
    """删除对白及其所有关联的音频文件（磁盘 + 历史记录）。返回 (是否成功, 删除文件数)。"""
    audio_dir = DATA_DIR / "audio"
    deleted_files = 0
    project = _read_project(project_id)
    if project is None:
        return False, 0
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    # 删除磁盘上的音频文件
                    for ah in dlg.get("audio_history", []):
                        fn = ah.get("filename", "")
                        if fn:
                            fp = audio_dir / fn
                            try:
                                if fp.exists():
                                    os.remove(str(fp))
                                    deleted_files += 1
                            except OSError:
                                pass
                    # 从对白列表中移除
                    ep["dialogues"] = [d for d in ep["dialogues"] if d["id"] != dialogue_id]
                    _write_project(project_id, project)
                    return True, deleted_files
    return False, 0


def delete_episode_all_dialogues(project_id: str, episode_id: str) -> tuple[bool, int, int]:
    """删除剧集所有对白及其关联音频文件。返回 (是否成功, 删除对白数, 删除文件数)。"""
    audio_dir = DATA_DIR / "audio"
    project = _read_project(project_id)
    if project is None:
        return False, 0, 0
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            dialogues = ep.get("dialogues", [])
            deleted_files = 0
            for dlg in dialogues:
                for ah in dlg.get("audio_history", []):
                    fn = ah.get("filename", "")
                    if fn:
                        fp = audio_dir / fn
                        try:
                            if fp.exists():
                                os.remove(str(fp))
                                deleted_files += 1
                        except OSError:
                            pass
            dlg_count = len(dialogues)
            ep["dialogues"] = []
            _write_project(project_id, project)
            return True, dlg_count, deleted_files
    return False, 0, 0


def add_audio_to_history(project_id: str, episode_id: str, dialogue_id: str,
                         audio_url: str, filename: str = "") -> dict | None:
    """Add a new audio entry to a dialogue's history and set as current."""
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    entry = {
                        "id": _uid(),
                        "url": audio_url,
                        "filename": filename or audio_url.split("/")[-1],
                        "created_at": _now(),
                    }
                    dlg["audio_history"].append(entry)
                    dlg["current_audio_id"] = entry["id"]
                    dlg["status"] = "completed"
                    _write_project(project_id, project)
                    return dlg
    return None


def set_current_audio(project_id: str, episode_id: str, dialogue_id: str, audio_id: str) -> dict | None:
    """Set a specific audio entry as the current (active) audio."""
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    # Verify the audio_id exists in history
                    ids = [a["id"] for a in dlg.get("audio_history", [])]
                    if audio_id not in ids:
                        return None
                    dlg["current_audio_id"] = audio_id
                    dlg["status"] = "completed"
                    _write_project(project_id, project)
                    return dlg
    return None


def remove_audio_from_history(project_id: str, episode_id: str, dialogue_id: str, audio_id: str) -> dict | None:
    """Remove a single audio entry from history. If it was the current audio, fall back to the most recent remaining."""
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    history = dlg.get("audio_history", [])
                    # Remove the entry
                    dlg["audio_history"] = [a for a in history if a["id"] != audio_id]
                    # If we deleted the current audio, fall back to the last one
                    if dlg.get("current_audio_id") == audio_id:
                        if dlg["audio_history"]:
                            dlg["current_audio_id"] = dlg["audio_history"][-1]["id"]
                        else:
                            dlg["current_audio_id"] = None
                            dlg["status"] = "pending"
                    _write_project(project_id, project)
                    return dlg
    return None


def clear_audio_history(project_id: str, episode_id: str, dialogue_id: str) -> dict | None:
    """Clear all audio history for a dialogue."""
    project = _read_project(project_id)
    if project is None:
        return None
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            for dlg in ep["dialogues"]:
                if dlg["id"] == dialogue_id:
                    dlg["audio_history"] = []
                    dlg["current_audio_id"] = None
                    dlg["status"] = "pending"
                    _write_project(project_id, project)
                    return dlg
    return None


# ─── Timeline ───────────────────────────────────────────────

def get_timeline(project_id: str, episode_id: str) -> dict | None:
    """Get timeline dict from episode, or None if not yet created."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        return None
    return ep.get("timeline")


def save_timeline(project_id: str, episode_id: str, timeline: dict) -> bool:
    """Write timeline dict into episode. Returns True on success."""
    project = _read_project(project_id)
    if project is None:
        return False
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            ep["timeline"] = timeline
            _write_project(project_id, project)
            return True
    return False


def _update_timeline_field(project_id: str, episode_id: str, updater) -> bool:
    """Generic helper: read timeline, apply updater(timeline), write back."""
    project = _read_project(project_id)
    if project is None:
        return False
    for ep in project["episodes"]:
        if ep["id"] == episode_id:
            timeline = ep.get("timeline")
            if timeline is None:
                return False
            updater(timeline)
            _write_project(project_id, project)
            return True
    return False


def add_track_to_timeline(project_id: str, episode_id: str, track: dict) -> bool:
    return _update_timeline_field(project_id, episode_id, lambda t: t["tracks"].append(track))


def update_track_in_timeline(project_id: str, episode_id: str, track_id: str, **fields) -> dict | None:
    result = [None]
    def updater(t):
        for tr in t["tracks"]:
            if tr["id"] == track_id:
                tr.update(fields)
                result[0] = tr
                break
    if _update_timeline_field(project_id, episode_id, updater):
        return result[0]
    return None


def delete_track_from_timeline(project_id: str, episode_id: str, track_id: str) -> bool:
    def updater(t):
        if len(t["tracks"]) <= 1:
            raise ValueError("Cannot delete the last track")
        t["tracks"] = [tr for tr in t["tracks"] if tr["id"] != track_id]
        t["clips"] = [c for c in t["clips"] if c["track_id"] != track_id]
    try:
        return _update_timeline_field(project_id, episode_id, updater)
    except ValueError:
        return False


def add_clip_to_timeline(project_id: str, episode_id: str, clip: dict) -> bool:
    return _update_timeline_field(project_id, episode_id, lambda t: t["clips"].append(clip))


def update_clip_in_timeline(project_id: str, episode_id: str, clip_id: str, **fields) -> dict | None:
    result = [None]
    def updater(t):
        for c in t["clips"]:
            if c["id"] == clip_id:
                c.update(fields)
                result[0] = c
                break
    if _update_timeline_field(project_id, episode_id, updater):
        return result[0]
    return None


def delete_clip_from_timeline(project_id: str, episode_id: str, clip_id: str) -> bool:
    def updater(t):
        before = len(t["clips"])
        t["clips"] = [c for c in t["clips"] if c["id"] != clip_id]
        return len(t["clips"]) < before
    return _update_timeline_field(project_id, episode_id, updater)


def add_imported_audio(project_id: str, episode_id: str, audio: dict) -> bool:
    def updater(t):
        if "imported_audio" not in t:
            t["imported_audio"] = []
        t["imported_audio"].append(audio)
    return _update_timeline_field(project_id, episode_id, updater)


def add_snapshot(project_id: str, episode_id: str, snapshot: dict) -> bool:
    def updater(t):
        if "snapshots" not in t:
            t["snapshots"] = []
        t["snapshots"].append(snapshot)
        if len(t["snapshots"]) > 10:
            t["snapshots"] = t["snapshots"][-10:]
    return _update_timeline_field(project_id, episode_id, updater)


def restore_snapshot(project_id: str, episode_id: str, version: int) -> dict | None:
    result = [None]
    def updater(t):
        for s in t.get("snapshots", []):
            if s["version"] == version:
                t["tracks"] = copy.deepcopy(s["tracks"])
                t["clips"] = copy.deepcopy(s["clips"])
                result[0] = t
                break
    if _update_timeline_field(project_id, episode_id, updater):
        return result[0]
    return None
# ─── Generation Task Status ───────────────────────────────

def _ensure_generation_tasks(project: dict) -> bool:
    """确保 project dict 中 generation_tasks 字段存在。Returns True if added."""
    if "generation_tasks" not in project:
        project["generation_tasks"] = {}
        return True
    return False


def init_generation_task(project_id: str, episode_id: str, task_type: str,
                         total: int = 0) -> str:
    """Initialize a generation task, return task_id."""
    p = _read_project(project_id)
    if p is None:
        return ""
    task_id = f"gen_task_{uuid.uuid4().hex[:8]}"
    _ensure_generation_tasks(p)
    p["generation_tasks"][task_id] = {
        "id": task_id,
        "episode_id": episode_id,
        "type": task_type,
        "status": "running",
        "current": 0,
        "total": total,
        "created_at": _now(),
        "updated_at": _now(),
        "error": None,
    }
    _write_project(project_id, p)
    return task_id


def update_generation_task(project_id: str, task_id: str, **fields) -> bool:
    """更新生成任务字段。"""
    p = _read_project(project_id)
    if p is None:
        return False
    if task_id in p.get("generation_tasks", {}):
        p["generation_tasks"][task_id].update(fields)
        p["generation_tasks"][task_id]["updated_at"] = _now()
        _write_project(project_id, p)
        return True
    return False


def get_generation_task(project_id: str, episode_id: str = None,
                        task_type: str = None) -> dict | None:
    """获取剧集最新的生成任务（优先返回 running 状态）。"""
    p = _read_project(project_id)
    if p is None:
        return None
    tasks = p.get("generation_tasks", {})
    candidates = []
    for tid, t in tasks.items():
        if episode_id and t.get("episode_id") != episode_id:
            continue
        if task_type and t.get("type") != task_type:
            continue
        candidates.append(t)
    if not candidates:
        return None
    running = [t for t in candidates if t.get("status") == "running"]
    if running:
        running.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
        return running[0]
    candidates.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return candidates[0]


def cancel_generation_task(project_id: str, task_id: str) -> bool:
    """取消一个正在运行的任务。将状态标记为 cancelled。"""
    p = _read_project(project_id)
    if p is None:
        return False
    if task_id in p.get("generation_tasks", {}):
        p["generation_tasks"][task_id]["status"] = "cancelled"
        p["generation_tasks"][task_id]["updated_at"] = _now()
        _write_project(project_id, p)
        return True
    return False


def list_generation_tasks(project_id: str, episode_id: str = None,
                          status: str = None) -> list[dict]:
    """列出项目的生成任务，按 updated_at 降序排列。

    Args:
        project_id: 项目 ID
        episode_id: 可选，按剧集过滤
        status: 可选，按状态过滤（running/complete/error/cancelled）

    Returns:
        任务列表，按更新时间降序
    """
    p = _read_project(project_id)
    if p is None:
        return []
    tasks = p.get("generation_tasks", {})
    result = []
    for tid, t in tasks.items():
        if episode_id and t.get("episode_id") != episode_id:
            continue
        if status and t.get("status") != status:
            continue
        result.append(t)
    result.sort(key=lambda t: t.get("updated_at", ""), reverse=True)
    return result
