from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session as OrmSession

from .config import settings
from .models import Base

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


REQUIRED_COLUMNS = {
    "users": {
        "id",
        "username",
        "password_hash",
        "totp_secret",
        "is_admin",
        "disabled_at",
        "approved_at",
        "welcomed_at",
        "session_version",
    },
    "tasks": {
        "id",
        "user_id",
        "title",
        "status",
        "day_date",
        "subtasks",
        "carried_count",
        "next_action",
        "deleted_at",
    },
}


def _is_duplicate_column_error(exc: OperationalError) -> bool:
    message = str(exc.orig).lower()
    return "duplicate column name" in message or "already exists" in message


def _assert_schema_ready() -> None:
    inspector = inspect(engine)
    missing: list[str] = []
    for table, required in REQUIRED_COLUMNS.items():
        existing = {col["name"] for col in inspector.get_columns(table)}
        for column in sorted(required - existing):
            missing.append(f"{table}.{column}")
    if missing:
        raise RuntimeError(f"Database schema missing required columns: {', '.join(missing)}")


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # Idempotent additive migrations
    with engine.begin() as conn:
        for ddl in [
            "ALTER TABLE users ADD COLUMN last_ritual_date DATE",
            "ALTER TABLE users ADD COLUMN stuck_threshold_days INTEGER DEFAULT 5",
            "ALTER TABLE tasks ADD COLUMN subtasks TEXT DEFAULT '[]'",
            "ALTER TABLE tasks ADD COLUMN effort VARCHAR(1)",
            "ALTER TABLE tasks ADD COLUMN carried_count INTEGER DEFAULT 0",
            "ALTER TABLE tasks ADD COLUMN next_action VARCHAR(500)",
            "ALTER TABLE tasks ADD COLUMN deleted_at DATETIME",
            # Multi-user columns
            "ALTER TABLE users ADD COLUMN username VARCHAR(80)",
            "ALTER TABLE users ADD COLUMN password_hash VARCHAR(200)",
            "ALTER TABLE users ADD COLUMN totp_secret VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0",
            "ALTER TABLE users ADD COLUMN disabled_at DATETIME",
            "ALTER TABLE users ADD COLUMN approved_at DATETIME",
            "ALTER TABLE users ADD COLUMN welcomed_at DATETIME",
            "ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)",
        ]:
            try:
                conn.execute(text(ddl))
            except OperationalError as exc:
                if not _is_duplicate_column_error(exc):
                    raise

        # Backfill: any pre-existing user predates the approval gate, so
        # auto-approve them at their original created_at. Idempotent — only
        # touches rows where approved_at is still NULL.
        conn.execute(text(
            "UPDATE users SET approved_at = created_at "
            "WHERE approved_at IS NULL AND created_at IS NOT NULL"
        ))
        conn.execute(text(
            "UPDATE users SET session_version = 1 "
            "WHERE session_version IS NULL"
        ))

    _assert_schema_ready()


def get_db():
    db: OrmSession = SessionLocal()
    try:
        yield db
    finally:
        db.close()
