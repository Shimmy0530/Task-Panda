from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import AIProviderUnavailable, require_ai_provider_configured, settings
from .db import engine, init_db
from .routers import auth as auth_router
from .routers import tasks as tasks_router
from .routers import sessions as sessions_router
from .routers.capture import capture_router, llm_router
from .routers import transcribe as transcribe_router
from .routers import morning as morning_router
from .routers import settings as settings_router
from .routers import admin as admin_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Focus", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.APP_BASE_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(tasks_router.router)
app.include_router(sessions_router.router)
app.include_router(capture_router)
app.include_router(llm_router)
app.include_router(transcribe_router.router)
app.include_router(morning_router.router)
app.include_router(settings_router.router)
app.include_router(admin_router.router)


@app.get("/api/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Health check database probe failed")
        raise HTTPException(503, "Database unavailable")
    return {"ok": True}


@app.get("/api/ai/ready")
def ai_ready():
    try:
        require_ai_provider_configured()
    except AIProviderUnavailable:
        return {"ready": False}
    return {"ready": True}
