from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import auth as auth_router
from .routers import tasks as tasks_router
from .routers import sessions as sessions_router
from .routers.capture import capture_router, llm_router
from .routers import transcribe as transcribe_router
from .routers import morning as morning_router
from .routers import settings as settings_router


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


@app.get("/api/health")
def health():
    return {"ok": True}
