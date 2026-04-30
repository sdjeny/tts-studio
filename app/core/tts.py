"""TTS client wrapper - fire-and-forget style.
submit 成功即返回 task_id，不等下载完成。
"""
import asyncio
import sys
from pathlib import Path

_tts_dir = Path(__file__).resolve().parent.parent / "api" / "qwen3-tts"
sys.path.insert(0, str(_tts_dir))

from tts_client import TtsClient

_client = None


def get_client():
    global _client
    if _client is None:
        _client = TtsClient.from_config()
    return _client


async def submit_tts(text: str, speaker: str = "", speed: float = 1.0,
                     pitch: float = 1.0, instruct: str = "",
                     language: str = "Chinese") -> str:
    """
    提交 TTS 任务，立即返回 task_id。
    失败则 raise Exception。
    instruct 格式：角色基础风格 + 场景情绪，如 '沉稳略带磁性，此处略带紧张'
    """
    client = get_client()

    full_instruct = instruct
    if speed != 1.0:
        full_instruct += f"，语速{speed:.1f}倍"
    if pitch != 1.0:
        full_instruct += f"，音调{pitch:.1f}倍"

    loop = asyncio.get_event_loop()

    def _submit():
        return client.submit(
            text=text,
            language=language,
            speaker=speaker,
            instruct=full_instruct.strip("，"),
        )

    submit_result = await loop.run_in_executor(None, _submit)
    if submit_result.error:
        raise Exception(f"TTS submit failed: {submit_result.error}")

    return submit_result.task_id


async def check_tts_status(task_id: str) -> dict:
    """
    查询一次 TTS 任务状态，不轮询。
    返回 {"status": "pending"|"processing"|"success"|"failed", "ok": bool, "error": str}
    """
    client = get_client()
    loop = asyncio.get_event_loop()

    def _check():
        return client.status(task_id)

    sr = await loop.run_in_executor(None, _check)
    return {
        "status": sr.status,
        "ok": sr.ok,
        "error": sr.error,
    }


async def download_tts(task_id: str) -> bytes:
    """
    等待 TTS 任务完成并下载音频。
    """
    client = get_client()
    loop = asyncio.get_event_loop()

    def _wait():
        return client.wait(task_id)

    status_result = await loop.run_in_executor(None, _wait)
    if not status_result.ok:
        raise Exception(f"TTS failed: {status_result.error or status_result.status}")

    def _download():
        return client.download(task_id)

    dl_result = await loop.run_in_executor(None, _download)
    if not dl_result.ok:
        raise Exception(f"TTS download failed: {dl_result.error}")

    return dl_result.data


async def generate_audio(text: str, speaker: str = "", speed: float = 1.0,
                         pitch: float = 1.0, instruct: str = "",
                         language: str = "Chinese") -> tuple[str, bytes]:
    """兼容旧接口：提交+等待+下载"""
    task_id = await submit_tts(text, speaker, speed, pitch, instruct, language)
    audio_data = await download_tts(task_id)
    return task_id, audio_data
