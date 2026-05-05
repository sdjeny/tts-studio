from fastapi import APIRouter
from app.core.voice_service import get_speakers

router = APIRouter()

@router.get("/voices")
async def api_list_voices():
    speakers = await get_speakers()
    return {"voices": speakers}