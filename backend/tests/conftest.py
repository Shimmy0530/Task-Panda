import os
from pathlib import Path

# Set env vars before importing anything from `app` — the engine is bound at
# import time from settings.DATABASE_URL, so this MUST run first.
os.environ.setdefault("JWT_SECRET", "test-secret")
TEST_DB_PATH = Path(os.environ.get("TEMP", "/tmp")) / "task-panda-tests.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"

import pytest

from app.db import SessionLocal, engine, init_db
from app.models import Base
from app.routers import auth as auth_router


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    auth_router._PENDING_TOTP.clear()
    init_db()
    yield


@pytest.fixture()
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
