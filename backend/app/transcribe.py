import httpx
from .config import require_ai_provider_configured, settings

TRANSCRIBE_PATH = "/audio/transcriptions"


async def transcribe_audio(audio_bytes: bytes, filename: str, mimetype: str) -> dict:
    """Send audio bytes to Groq Whisper. Returns dict with 'text', 'duration', 'language'."""
    require_ai_provider_configured()
    async with httpx.AsyncClient(timeout=120) as client:
        files = {"file": (filename, audio_bytes, mimetype)}
        data = {
            "model": settings.WHISPER_MODEL,
            "response_format": "verbose_json",
            "temperature": "0",
            "language": "en",
        }
        r = await client.post(
            f"{settings.LLM_BASE_URL}{TRANSCRIBE_PATH}",
            headers={"Authorization": f"Bearer {settings.LLM_API_KEY}"},
            files=files,
            data=data,
        )
        r.raise_for_status()
        return r.json()
