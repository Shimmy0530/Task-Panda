import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..config import AIProviderUnavailable
from ..db import get_db
from ..llm import outline_from_transcript
from ..models import Task, User
from ..transcribe import transcribe_audio
from .tasks import _visible_tasks

router = APIRouter(prefix="/api", tags=["voice"])
logger = logging.getLogger(__name__)

MAX_AUDIO_BYTES = 25 * 1024 * 1024  # Groq Whisper limit


@router.post("/transcribe")
async def transcribe_endpoint(
    file: UploadFile = File(...),
    user: User = Depends(current_user),
):
    audio = await file.read()
    if len(audio) == 0:
        raise HTTPException(400, "Empty file.")
    if len(audio) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Audio too large (25 MB max). Record shorter or split.")

    try:
        result = await transcribe_audio(
            audio,
            file.filename or "recording.webm",
            file.content_type or "audio/webm",
        )
    except AIProviderUnavailable:
        logger.info("Transcription requested without AI provider configuration")
        raise HTTPException(503, "Transcription service unavailable. Try again later.")
    except Exception:  # noqa: BLE001
        logger.exception("Transcription provider request failed")
        raise HTTPException(503, "Transcription service unavailable. Try again later.")

    return {
        "transcript": result.get("text", "").strip(),
        "duration": result.get("duration"),
        "language": result.get("language"),
    }


class OutlineRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=20000)
    task_id: int | None = None


@router.post("/outline")
async def outline_endpoint(
    payload: OutlineRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task_title = task_notes = None
    if payload.task_id:
        task = (
            _visible_tasks(db.query(Task))
            .filter(Task.id == payload.task_id, Task.user_id == user.id)
            .first()
        )
        if task:
            task_title = task.title
            task_notes = task.notes
    try:
        outline = await outline_from_transcript(payload.transcript, task_title, task_notes)
    except AIProviderUnavailable:
        logger.info("Outline requested without AI provider configuration")
        raise HTTPException(503, "AI service unavailable. Try again later.")
    except Exception:  # noqa: BLE001
        logger.exception("Outline provider request failed")
        raise HTTPException(503, "AI service unavailable. Try again later.")
    return {"outline": outline}
