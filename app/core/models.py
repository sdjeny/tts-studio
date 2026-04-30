"""Pydantic models for the TTS Studio web server."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ProjectCharacter:
    """A character (voice role) within a project."""

    def __init__(
        self,
        name: str,
        voice_id: str = "Cherry",
        speed: float = 1.0,
        pitch: float = 1.0,
        id: str | None = None,
    ):
        self.id = id or _new_id("char")
        self.name = name
        self.voice_id = voice_id
        self.speed = speed
        self.pitch = pitch

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "voice_id": self.voice_id, "speed": self.speed, "pitch": self.pitch}

    @staticmethod
    def from_dict(d: dict) -> "ProjectCharacter":
        return ProjectCharacter(id=d["id"], name=d["name"], voice_id=d.get("voice_id", "Cherry"), speed=d.get("speed", 1.0), pitch=d.get("pitch", 1.0))


class AudioRecord:
    """One audio generation record in history."""

    def __init__(self, url: str, status: str = "completed", id: str | None = None, created_at: str | None = None):
        self.id = id or _new_id("audio")
        self.url = url
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {"id": self.id, "url": self.url, "status": self.status, "created_at": self.created_at}

    @staticmethod
    def from_dict(d: dict) -> "AudioRecord":
        return AudioRecord(id=d["id"], url=d["url"], status=d.get("status", "completed"), created_at=d.get("created_at"))


class DialogueStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Dialogue:
    """A single line of dialogue."""

    def __init__(
        self,
        text: str,
        character_id: str,
        id: str | None = None,
        status: str = DialogueStatus.PENDING,
        audio_history: list | None = None,
        order: int = 0,
    ):
        self.id = id or _new_id("dlg")
        self.text = text
        self.character_id = character_id
        self.status = status
        self.audio_history = [AudioRecord.from_dict(a) for a in audio_history] if audio_history else []
        self.order = order

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "character_id": self.character_id,
            "status": self.status,
            "audio_history": [a.to_dict() for a in self.audio_history],
            "order": self.order,
        }

    @staticmethod
    def from_dict(d: dict) -> "Dialogue":
        return Dialogue(
            id=d["id"],
            text=d["text"],
            character_id=d["character_id"],
            status=d.get("status", DialogueStatus.PENDING),
            audio_history=d.get("audio_history"),
            order=d.get("order", 0),
        )


class Episode:
    """An episode containing dialogues."""

    def __init__(self, title: str, id: str | None = None, dialogues: list | None = None, created_at: str | None = None):
        self.id = id or _new_id("ep")
        self.title = title
        self.dialogues = [Dialogue.from_dict(d) for d in dialogues] if dialogues else []
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {"id": self.id, "title": self.title, "dialogues": [d.to_dict() for d in self.dialogues], "created_at": self.created_at}

    @staticmethod
    def from_dict(d: dict) -> "Episode":
        return Episode(id=d["id"], title=d["title"], dialogues=d.get("dialogues"), created_at=d.get("created_at"))


class Project:
    """Top-level project."""

    def __init__(
        self, name: str, id: str | None = None, characters: list | None = None, episodes: list | None = None, created_at: str | None = None
    ):
        self.id = id or _new_id("proj")
        self.name = name
        self.characters = [ProjectCharacter.from_dict(c) for c in characters] if characters else []
        self.episodes = [Episode.from_dict(e) for e in episodes] if episodes else []
        self.created_at = created_at or datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "characters": [c.to_dict() for c in self.characters],
            "episodes": [e.to_dict() for e in self.episodes],
            "created_at": self.created_at,
        }

    @staticmethod
    def from_dict(d: dict) -> "Project":
        return Project(id=d["id"], name=d["name"], characters=d.get("characters"), episodes=d.get("episodes"), created_at=d.get("created_at"))