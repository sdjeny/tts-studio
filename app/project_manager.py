import json
import os
import uuid
from dataclasses import asdict
from typing import List
from .models import Project, ScriptLine, AudioClip, Character
from .config import AUDIO_DIR

def script_lines_to_clips(lines: List[ScriptLine]) -> List[AudioClip]:
    """将剧本行转换为音频片段（尚未生成）"""
    clips = []
    for i, line in enumerate(lines):
        if line.type in ("dialogue", "narration") and line.text.strip():
            clip = AudioClip(
                id=uuid.uuid4().hex[:8],
                type="dialogue",
                character=line.character,
                text=line.text,
                file_path=str(AUDIO_DIR / f"clip_{i:04d}_{uuid.uuid4().hex[:4]}.mp3"),
                voice=line.voice,
                rate=line.rate,
                pitch=line.pitch,
                volume=1.0,
                start_time=sum(c.duration for c in clips) if clips else 0.0,
                duration=0.0,
                is_generated=False
            )
            clips.append(clip)
    return clips

def load_project_from_file(path: str) -> Project:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    p = Project(name=data.get("name", "未命名"))
    p.raw_text = data.get("raw_text", "")
    p.script_lines = [ScriptLine(**l) for l in data.get("script_lines", [])]
    p.llm_config = data.get("llm_config", {})
    p.character_voices = data.get("character_voices", {})
    
    # 🔑 加载角色列表（兼容旧工程）
    if "characters" in data:
        p.characters = [Character(**c) for c in data.get("characters", [])]
    
    for c in data.get("audio_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.audio_clips.append(clip)
    for c in data.get("bgm_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.bgm_clips.append(clip)
    for c in data.get("sfx_clips", []):
        clip = AudioClip(**c)
        clip.is_generated = os.path.exists(clip.file_path)
        p.sfx_clips.append(clip)
    
    return p

def save_project_to_file(project: Project, path: str):
    data = {
        "name": project.name,
        "raw_text": project.raw_text,
        "script_lines": [asdict(l) for l in project.script_lines],
        "audio_clips": [asdict(c) for c in project.audio_clips],
        "bgm_clips": [asdict(c) for c in project.bgm_clips],
        "sfx_clips": [asdict(c) for c in project.sfx_clips],
        "llm_config": project.llm_config,
        "characters": [asdict(c) for c in project.characters],  # 🔑 保存角色列表
        "character_voices": project.character_voices  # 向后兼容
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
