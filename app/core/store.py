"""JSON file-based persistence layer."""
import json
import uuid
import time
import os
import copy
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DATA_FILE = DATA_DIR / "studio.json"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        _write({"projects": []})


def _read() -> dict:
    _ensure_data_dir()
    if not DATA_FILE.exists():
        _write({"projects": []})
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(data: dict):
    tmp = str(DATA_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Windows 下 os.replace 可能因文件锁定而失败，加重试
    for attempt in range(5):
        try:
            os.replace(tmp, str(DATA_FILE))
            return
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.5 * (attempt + 1))
    # 清理临时文件
    try:
        os.remove(tmp)
    except OSError:
        pass


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _uid() -> str:
    return uuid.uuid4().hex[:12]


# ─── Projects ────────────────────────────────────────────────

def list_projects() -> list[dict]:
    data = _read()
    projects = data["projects"]
    # 数据迁移
    dirty = False
    for p in projects:
        if not p.get("updated_at"):
            p["updated_at"] = p.get("created_at", "")
            dirty = True
        # 迁移：旧项目补充 tts_defaults 默认值
        if not p.get("tts_defaults"):
            p["tts_defaults"] = {
                "temperature": 0.3,
                "do_sample": True,
                "top_k": 20,
                "top_p": 0.85,
                "repetition_penalty": 1.1,
            }
            dirty = True
    if dirty:
        _write(data)
    # 按 updated_at 倒序排列
    return sorted(projects, key=lambda p: p.get("updated_at", ""), reverse=True)


def get_project(project_id: str) -> dict | None:
    for p in _read()["projects"]:
        if p["id"] == project_id:
            return p
    return None


def create_project(name: str) -> dict:
    _ensure_data_dir()
    data = _read()
    now = _now()
    project = {
        "id": _uid(),
        "name": name,
        "created_at": now,
        "updated_at": now,
        "characters": [],
        "episodes": [],
        # ── 项目级 TTS 默认参数 ────────────────────────────────
        # 当对白生成音频时未显式指定采样参数，则使用此处的值。
        # 保守默认值旨在最小化不同句子间的声音波动。
        "tts_defaults": {
            "temperature": 0.3,          # 采样温度，越低越稳定（官方默认 0.9）
            "do_sample": True,           # True=采样 / False=贪心解码
            "top_k": 20,                 # top-k 采样，越小越集中（官方默认 50）
            "top_p": 0.85,               # 核采样阈值，越小越集中（官方默认 1.0）
            "repetition_penalty": 1.1,   # 重复惩罚（官方默认 1.05）
        },
    }
    data["projects"].append(project)
    _write(data)
    return project


def update_project(project_id: str, name: str | None = None, **extra) -> dict | None:
    """更新项目字段。name 之外的字段（如 tts_defaults）通过 **extra 传入。"""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            if name is not None:
                p["name"] = name
            if extra:
                # 深度合并：对于嵌套 dict（如 tts_defaults），逐字段更新而非整体替换
                for k, v in extra.items():
                    if isinstance(v, dict) and isinstance(p.get(k), dict):
                        p[k].update(v)
                    else:
                        p[k] = v
            _write(data)
            return p
    return None


def touch_project(project_id: str) -> None:
    """更新项目的 updated_at 时间戳。"""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            p["updated_at"] = _now()
            _write(data)
            return


def delete_project(project_id: str) -> bool:
    data = _read()
    projects = [p for p in data["projects"] if p["id"] != project_id]
    if len(projects) == len(data["projects"]):
        return False
    data["projects"] = projects
    _write(data)
    return True


# ─── Characters ──────────────────────────────────────────────

def project_characters(project_id: str) -> list[dict]:
    p = get_project(project_id)
    return p["characters"] if p else []


def add_character(project_id: str, name: str, voice_id: str, speed: float = 1.0,
                  pitch: float = 1.0, description: str = "",
                  audio_effects: list | None = None, **extra) -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
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
            p["characters"].append(char)
            _write(data)
            return char
    return None


def update_character(project_id: str, char_id: str, **fields) -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for c in p["characters"]:
                if c["id"] == char_id:
                    c.update(fields)
                    _write(data)
                    return c
    return None


def delete_character(project_id: str, char_id: str) -> bool:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            before = len(p["characters"])
            p["characters"] = [c for c in p["characters"] if c["id"] != char_id]
            if len(p["characters"]) < before:
                _write(data)
                return True
    return False


# ─── Episodes ────────────────────────────────────────────────

def project_episodes(project_id: str) -> list[dict]:
    p = get_project(project_id)
    return p["episodes"] if p else []


def get_episode(project_id: str, episode_id: str) -> dict | None:
    p = get_project(project_id)
    if not p:
        return None
    for ep in p["episodes"]:
        if ep["id"] == episode_id:
            return ep
    return None


def create_episode(project_id: str, title: str) -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            ep = {
                "id": _uid(),
                "title": title,
                "summary": "",
                "style_enabled": False,  # 剧集默认关闭风格
                "created_at": _now(),
                "dialogues": [],
            }
            p["episodes"].append(ep)
            _write(data)
            return ep
    return None


def update_episode(project_id: str, episode_id: str, **fields) -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    ep.update(fields)
                    _write(data)
                    return ep
    return None


def delete_episode(project_id: str, episode_id: str) -> bool:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            before = len(p["episodes"])
            p["episodes"] = [ep for ep in p["episodes"] if ep["id"] != episode_id]
            if len(p["episodes"]) < before:
                _write(data)
                return True
    return False


# ─── Dialogues ───────────────────────────────────────────────

def episode_dialogues(project_id: str, episode_id: str) -> list[dict]:
    ep = get_episode(project_id, episode_id)
    return ep["dialogues"] if ep else []


def add_dialogue(project_id: str, episode_id: str, character_id: str,
                 text: str, order: int = 0, instruct: str = "") -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    # resolve character name（仅从真实角色查找）
                    char_name = ""
                    for c in p["characters"]:
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
                    _write(data)
                    return dlg
    return None


def update_dialogue(project_id: str, episode_id: str, dialogue_id: str, **fields) -> dict | None:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    for dlg in ep["dialogues"]:
                        if dlg["id"] == dialogue_id:
                            dlg.update(fields)
                            # 如果更新了 character_id，自动同步 character_name
                            if "character_id" in fields:
                                cid = fields["character_id"]
                                char_name = ""
                                for c in p["characters"]:
                                    if c["id"] == cid:
                                        char_name = c["name"]
                                        break
                                dlg["character_name"] = char_name or f"⚠ 角色异常({cid[:8]})"
                            _write(data)
                            return dlg
    return None

# Helper: update only status
def update_dialogue_status(project_id: str, episode_id: str, dialogue_id: str,
                           status: str) -> dict | None:
    return update_dialogue(project_id, episode_id, dialogue_id, status=status)


def delete_dialogue(project_id: str, episode_id: str, dialogue_id: str) -> bool:
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    before = len(ep["dialogues"])
                    ep["dialogues"] = [d for d in ep["dialogues"] if d["id"] != dialogue_id]
                    if len(ep["dialogues"]) < before:
                        _write(data)
                        return True
    return False


def insert_dialogue_after(project_id: str, episode_id: str, after_dialogue_id: str,
                         character_id: str = "", text: str = "", instruct: str = "") -> tuple[dict | None, int]:
    """在指定对白之后插入一条新对白。返回 (新对白 dict, affected 数量)，或 (None, 0)（找不到目标）。"""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
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
                    for c in p["characters"]:
                        if c["id"] == character_id:
                            char_name = c["name"]
                            break
                    if not char_name and p["characters"]:
                        char_name = p["characters"][0]["name"]
                        character_id = p["characters"][0]["id"]
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
                    _write(data)
                    return new_dlg, affected
    return None, 0


def delete_dialogue_and_audio_files(project_id: str, episode_id: str, dialogue_id: str) -> tuple[bool, int]:
    """删除对白及其所有关联的音频文件（磁盘 + 历史记录）。返回 (是否成功, 删除文件数)。"""
    audio_dir = DATA_DIR / "audio"
    deleted_files = 0
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
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
                            _write(data)
                            return True, deleted_files
    return False, 0


def delete_episode_all_dialogues(project_id: str, episode_id: str) -> tuple[bool, int, int]:
    """删除剧集所有对白及其关联音频文件。返回 (是否成功, 删除对白数, 删除文件数)。"""
    audio_dir = DATA_DIR / "audio"
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
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
                    _write(data)
                    return True, dlg_count, deleted_files
    return False, 0, 0


def add_audio_to_history(project_id: str, episode_id: str, dialogue_id: str,
                         audio_url: str, filename: str = "") -> dict | None:
    """Add a new audio entry to a dialogue's history and set as current."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
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
                            _write(data)
                            return dlg
    return None


def set_current_audio(project_id: str, episode_id: str, dialogue_id: str, audio_id: str) -> dict | None:
    """Set a specific audio entry as the current (active) audio."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    for dlg in ep["dialogues"]:
                        if dlg["id"] == dialogue_id:
                            # Verify the audio_id exists in history
                            ids = [a["id"] for a in dlg.get("audio_history", [])]
                            if audio_id not in ids:
                                return None
                            dlg["current_audio_id"] = audio_id
                            dlg["status"] = "completed"
                            _write(data)
                            return dlg
    return None


def remove_audio_from_history(project_id: str, episode_id: str, dialogue_id: str, audio_id: str) -> dict | None:
    """Remove a single audio entry from history. If it was the current audio, fall back to the most recent remaining."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
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
                            _write(data)
                            return dlg
    return None


def clear_audio_history(project_id: str, episode_id: str, dialogue_id: str) -> dict | None:
    """Clear all audio history for a dialogue."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    for dlg in ep["dialogues"]:
                        if dlg["id"] == dialogue_id:
                            dlg["audio_history"] = []
                            dlg["current_audio_id"] = None
                            dlg["status"] = "pending"
                            _write(data)
                            return dlg
    return None


def update_dialogue_status(project_id: str, episode_id: str, dialogue_id: str,
                           status: str) -> dict | None:
    return update_dialogue(project_id, episode_id, dialogue_id, status=status)


# ─── Timeline ───────────────────────────────────────────────

def get_timeline(project_id: str, episode_id: str) -> dict | None:
    """Get timeline dict from episode, or None if not yet created."""
    ep = get_episode(project_id, episode_id)
    if not ep:
        return None
    return ep.get("timeline")


def save_timeline(project_id: str, episode_id: str, timeline: dict) -> bool:
    """Write timeline dict into episode. Returns True on success."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    ep["timeline"] = timeline
                    _write(data)
                    return True
    return False


def _update_timeline_field(project_id: str, episode_id: str, updater) -> bool:
    """Generic helper: read timeline, apply updater(timeline), write back."""
    data = _read()
    for p in data["projects"]:
        if p["id"] == project_id:
            for ep in p["episodes"]:
                if ep["id"] == episode_id:
                    timeline = ep.get("timeline")
                    if timeline is None:
                        return False
                    updater(timeline)
                    _write(data)
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