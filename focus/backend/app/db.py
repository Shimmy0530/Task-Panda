from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, Session as OrmSession

from .config import settings
from .models import Base, User

OWNER_ID = 1

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)

    # Idempotent additive migrations
    with engine.begin() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN last_ritual_date DATE"))
        except OperationalError:
            pass
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN stuck_threshold_days INTEGER DEFAULT 5"))
        except OperationalError:
            pass
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN subtasks TEXT DEFAULT '[]'"))
        except OperationalError:
            pass
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN effort VARCHAR(1)"))
        except OperationalError:
            pass
        try:
            conn.execute(text("ALTER TABLE tasks ADD COLUMN carried_count INTEGER DEFAULT 0"))
        except OperationalError:
            pass

    # Bootstrap single owner
    with SessionLocal() as db:
        owner = db.get(User, OWNER_ID)
        if not owner:
            owner = User(id=OWNER_ID)
            db.add(owner)
            db.commit()


def get_db():
    db: OrmSession = SessionLocal()
    try:
        yield db
    finally:
        db.close()
