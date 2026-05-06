from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Boolean, DateTime, Date, ForeignKey, Text, Index
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    """Single owner. Bootstrapped at startup."""
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_ritual_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_frog: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    day_date: Mapped[date] = mapped_column(Date, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    sessions = relationship("Session", back_populates="task", cascade="all,delete")

    __table_args__ = (Index("ix_tasks_user_day", "user_id", "day_date"),)


class Session(Base):
    __tablename__ = "sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    duration_planned_seconds: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    task = relationship("Task", back_populates="sessions")


class Capture(Base):
    __tablename__ = "captures"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
