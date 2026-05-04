"""Project & Character CRUD API."""
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.core.store import (
    list_projects, get_project, create_project, update_project, delete_project,
    project_characters, add_character, update_character, delete_character,
    touch_project,
)

from app.core.audio_effects import (
    get_effects_registry,
    get_builtin_presets,
    validate_effects_chain,
    apply_effects_to_file,
    BUILTIN_PRESETS,
)

router = APIRouter()


# ── schemas ────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str


class TtsDefaults(BaseModel):
    """项目级 TTS 采样参数默认值。所有字段可选，None 表示不更新该字段。"""
    temperature: float | None = None
    do_sample: bool | None = None
    top_k: int | None = None
    top_p: float | None = None
    repetition_penalty: float | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    tts_defaults: TtsDefaults | None = None


class CharacterCreate(BaseModel):
    name: str
    voice_id: str = "Cherry"
    speed: float = 1.0
    pitch: float = 1.0
    description: str = ""
    base_instruct: str = ""
    audio_effects: list[dict] = []


class CharacterUpdate(BaseModel):
    name: str | None = None
    voice_id: str | None = None
    speed: float | None = None
    pitch: float | None = None
    description: str | None = None
    base_instruct: str | None = None
    audio_effects: list[dict] | None = None


# ── project endpoints ──────────────────────────────────

@router.get("/projects")
async def api_list_projects():
    return list_projects()


@router.get("/projects/defaults")
async def api_get_global_defaults():
    """返回全局 TTS 默认参数（从 config.yaml 读取）。"""
    from app.core.store import _load_tts_defaults
    return _load_tts_defaults()


@router.get("/projects/{project_id}")
async def api_get_project(project_id: str):
    p = get_project(project_id)
    if not p:
        raise HTTPException(404, "Project not found")
    return p


@router.post("/projects")
async def api_create_project(body: ProjectCreate):
    return create_project(body.name)


@router.patch("/projects/{project_id}")
async def api_update_project(project_id: str, body: ProjectUpdate):
    # 收集需要更新的字段
    extra = {}
    if body.tts_defaults is not None:
        # 只传入非 None 的字段，None 表示"不修改"
        tts_fields = {k: v for k, v in body.tts_defaults.model_dump().items() if v is not None}
        if tts_fields:
            extra["tts_defaults"] = tts_fields
    p = update_project(project_id, name=body.name, **extra)
    if not p:
        raise HTTPException(404, "Project not found")
    touch_project(project_id)
    return p


@router.delete("/projects/{project_id}")
async def api_delete_project(project_id: str):
    if not delete_project(project_id):
        raise HTTPException(404, "Project not found")
    return {"ok": True}


# ── character endpoints ────────────────────────────────

@router.get("/projects/{project_id}/characters")
async def api_list_characters(project_id: str):
    return project_characters(project_id)


@router.post("/projects/{project_id}/characters")
async def api_add_character(project_id: str, body: CharacterCreate):
    if not get_project(project_id):
        raise HTTPException(404, "Project not found")
    char = add_character(
        project_id, body.name, body.voice_id,
        body.speed, body.pitch, body.description,
        audio_effects=body.audio_effects,
        base_instruct=body.base_instruct,
    )
    touch_project(project_id)
    return char


@router.patch("/projects/{project_id}/characters/{char_id}")
async def api_update_character(project_id: str, char_id: str, body: CharacterUpdate):
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    c = update_character(project_id, char_id, **fields)
    if not c:
        raise HTTPException(404, "Character not found")
    touch_project(project_id)
    return c


@router.delete("/projects/{project_id}/characters/{char_id}")
async def api_delete_character(project_id: str, char_id: str):
    if not delete_character(project_id, char_id):
        raise HTTPException(404, "Character not found")
    touch_project(project_id)
    return {"ok": True}


# ── Audio effects APIs ──────────────────────────────────

@router.get("/audio-effects/registry")
async def api_get_effects_registry():
    """返回所有可用的效果类型及其参数定义（供前端构建效果编辑器 UI）。"""
    return get_effects_registry()


@router.get("/audio-effects/presets")
async def api_get_effects_presets():
    """返回所有内置效果预设。"""
    return get_builtin_presets()


class EffectsPreviewRequest(BaseModel):
    """效果预览：上传一段音频 + 效果链，返回处理后的音频。"""
    effects_chain: list[dict]
    character_id: str | None = None  # 可选：指定角色，优先从该角色的对白中找音频


@router.post("/projects/{project_id}/audio-effects/preview")
async def api_preview_effects(project_id: str, body: EffectsPreviewRequest):
    """
    效果预览：从项目中取最近一条已完成音频，应用效果链后返回处理后的 WAV。
    优先使用指定角色的音频，未指定则取全局最近一条。
    """
    proj = get_project(project_id)
    if not proj:
        raise HTTPException(404, "Project not found")

    def _find_audio(exclude_char_id=None, require_char_id=None):
        """遍历项目找最近一条有音频的对白，返回文件路径。"""
        for ep in reversed(proj.get("episodes", [])):
            for dlg in reversed(ep.get("dialogues", [])):
                cid = dlg.get("character_id", "")
                if exclude_char_id and cid == exclude_char_id:
                    continue
                if require_char_id and cid != require_char_id:
                    continue
                audio_id = dlg.get("current_audio_id")
                if not audio_id:
                    continue
                for ah in dlg.get("audio_history", []):
                    if ah.get("id") == audio_id and ah.get("filename"):
                        p = Path(__file__).resolve().parent.parent.parent / "data" / "audio" / ah["filename"]
                        if p.exists():
                            return str(p)
        return None

    # 优先从指定角色找，fallback 到全部
    source_path = _find_audio(require_char_id=body.character_id) if body.character_id else None
    if not source_path:
        source_path = _find_audio()

    if not source_path:
        raise HTTPException(
            400,
            "项目中没有可用的音频文件。请先生成一条音频（点击对白旁的生成按钮，完成后刷新状态）。"
        )

    error = validate_effects_chain(body.effects_chain)
    if error:
        raise HTTPException(400, error)

    import io
    import soundfile as sf
    from app.core.audio_effects import apply_effects

    audio, sr = sf.read(source_path, dtype="float32")
    processed = apply_effects(audio, sr, body.effects_chain)

    buf = io.BytesIO()
    sf.write(buf, processed, sr, format="WAV")

    from fastapi.responses import Response
    return Response(content=buf.getvalue(), media_type="audio/wav")