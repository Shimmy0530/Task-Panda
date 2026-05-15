from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy.exc import OperationalError

from app.config import Settings
from app.main import health
from app.models import User
from app.routers import transcribe as transcribe_router


def test_settings_allows_missing_llm_api_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    settings = Settings(_env_file=None, JWT_SECRET="test-secret")

    assert settings.LLM_API_KEY is None


def test_health_checks_database_connectivity(monkeypatch):
    class BrokenConnection:
        def __enter__(self):
            raise OperationalError("SELECT 1", {}, Exception("database missing"))

        def __exit__(self, exc_type, exc, tb):
            return False

    class BrokenEngine:
        def connect(self):
            return BrokenConnection()

    monkeypatch.setattr("app.main.engine", BrokenEngine())

    with pytest.raises(HTTPException) as exc:
        health()

    assert exc.value.status_code == 503
    assert exc.value.detail == "Database unavailable"


@pytest.mark.asyncio
async def test_transcribe_endpoint_hides_provider_exception(monkeypatch):
    async def failing_transcribe(audio_bytes, filename, mimetype):
        raise RuntimeError("provider leaked secret details")

    monkeypatch.setattr(transcribe_router, "transcribe_audio", failing_transcribe)
    upload = UploadFile(filename="voice.webm", file=BytesIO(b"audio"))
    user = User(id=1, username="owner", password_hash="x")

    with pytest.raises(HTTPException) as exc:
        await transcribe_router.transcribe_endpoint(upload, user=user)

    assert exc.value.status_code == 503
    assert exc.value.detail == "Transcription service unavailable. Try again later."
