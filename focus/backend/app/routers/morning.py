from datetime import date as Date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Task, User

router = APIRouter(prefix="/api/morning", tags=["morning"])

STALE_BACKLOG_DAYS = 30


class CarryAction(BaseModel):
    task_id: int
    action: Literal["carry", "drop", "done"]


class MorningComplete(BaseModel):
    today_date: Date
    yesterday_actions: list[CarryAction] = Field(default_factory=list)
    frog_title: str = Field(min_length=1, max_length=200)
    frog_notes: str | None = None
    supporting_titles: list[str] = Field(default_factory=list)
    pull_from_backlog: list[int] = Field(default_factory=list)
    dropped_stale_ids: list[int] = Field(default_factory=list)
    kept_stale_ids: list[int] = Field(default_factory=list)


def _serialize_task(t: Task) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "is_frog": t.is_frog,
        "notes": t.notes,
        "status": t.status,
        "subtasks": t.subtasks or [],
        "effort": t.effort,
        "carried_count": t.carried_count,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


@router.get("/state")
def morning_state(
    today: Date,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Return everything the wizard needs."""
    yesterday = Date.fromordinal(today.toordinal() - 1)
    yest_open = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.day_date == yesterday,
            Task.status.in_(["pending", "active"]),
        )
        .order_by(Task.is_frog.desc(), Task.created_at.asc())
        .all()
    )
    today_tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.day_date == today)
        .order_by(Task.is_frog.desc(), Task.created_at.asc())
        .all()
    )

    backlog = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.day_date.is_(None))
        .order_by(Task.created_at.desc())
        .all()
    )
    threshold = datetime.utcnow() - timedelta(days=STALE_BACKLOG_DAYS)
    stale_backlog = [t for t in backlog if t.created_at and t.created_at < threshold]
    backlog_top = backlog[:10]

    stuck_yesterday = [
        t.id for t in yest_open if t.carried_count >= user.stuck_threshold_days
    ]

    return {
        "yesterday_open": [_serialize_task(t) for t in yest_open],
        "today_existing": [_serialize_task(t) for t in today_tasks],
        "ritual_done": user.last_ritual_date == today,
        "stuck_yesterday": stuck_yesterday,
        "stuck_threshold_days": user.stuck_threshold_days,
        "stale_backlog": [_serialize_task(t) for t in stale_backlog],
        "backlog_top": [_serialize_task(t) for t in backlog_top],
    }


@router.post("/complete")
def complete(
    payload: MorningComplete,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    today = payload.today_date
    now = datetime.utcnow()

    # 1. Yesterday actions — carry prunes done subtasks and bumps carried_count.
    for ca in payload.yesterday_actions:
        task = (
            db.query(Task)
            .filter(Task.id == ca.task_id, Task.user_id == user.id)
            .first()
        )
        if not task:
            continue
        if ca.action == "carry":
            task.day_date = today
            task.status = "pending"
            task.is_frog = False  # carrying demotes; must re-pick frog
            task.subtasks = [s for s in (task.subtasks or []) if not s.get("done")]
            task.carried_count = (task.carried_count or 0) + 1
        elif ca.action == "done":
            task.status = "done"
            if not task.completed_at:
                task.completed_at = now
            task.carried_count = 0
        elif ca.action == "drop":
            task.status = "skipped"
            task.carried_count = 0

    db.flush()

    # 2. Frog handling — replace any existing frog for today.
    existing_today_frog = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.day_date == today,
            Task.is_frog == True,  # noqa: E712
        )
        .first()
    )
    if existing_today_frog:
        if existing_today_frog.title.strip() != payload.frog_title.strip():
            existing_today_frog.is_frog = False
            db.flush()
            db.add(Task(
                user_id=user.id,
                title=payload.frog_title.strip(),
                notes=payload.frog_notes,
                is_frog=True,
                day_date=today,
                subtasks=[],
            ))
    else:
        db.add(Task(
            user_id=user.id,
            title=payload.frog_title.strip(),
            notes=payload.frog_notes,
            is_frog=True,
            day_date=today,
            subtasks=[],
        ))

    db.flush()

    # 3. Supporting tasks (max 2; skip duplicates).
    today_titles = {
        t.title.lower()
        for t in db.query(Task).filter(Task.user_id == user.id, Task.day_date == today).all()
    }

    added = 0
    for raw in payload.supporting_titles:
        if added >= 2:
            break
        title = (raw or "").strip()
        if not title:
            continue
        if title.lower() in today_titles:
            continue
        db.add(Task(user_id=user.id, title=title, day_date=today, subtasks=[]))
        today_titles.add(title.lower())
        added += 1

    db.flush()

    # 4. Pull selected backlog items into today (resets carried_count).
    if payload.pull_from_backlog:
        pulls = (
            db.query(Task)
            .filter(
                Task.id.in_(payload.pull_from_backlog),
                Task.user_id == user.id,
                Task.day_date.is_(None),
            )
            .all()
        )
        for t in pulls:
            t.day_date = today
            t.carried_count = 0
        db.flush()

    # Day cap of 5 enforced over the union of carries + frog + supporting + pulls.
    today_count = (
        db.query(Task).filter(Task.user_id == user.id, Task.day_date == today).count()
    )
    if today_count > 5:
        db.rollback()
        raise HTTPException(
            400,
            f"Today would have {today_count} tasks. Max 5 — drop carries, supporting tasks, or pulls.",
        )

    # 5. Stale-backlog acknowledgements.
    if payload.kept_stale_ids:
        kept = (
            db.query(Task)
            .filter(
                Task.id.in_(payload.kept_stale_ids),
                Task.user_id == user.id,
                Task.day_date.is_(None),
            )
            .all()
        )
        for t in kept:
            t.created_at = now  # re-stamp to suppress stale prompt for another 30 days
    if payload.dropped_stale_ids:
        # Hard delete — user-acknowledged trash.
        dropped = (
            db.query(Task)
            .filter(
                Task.id.in_(payload.dropped_stale_ids),
                Task.user_id == user.id,
                Task.day_date.is_(None),
            )
            .all()
        )
        for t in dropped:
            db.delete(t)

    # 6. Mark ritual done.
    user.last_ritual_date = today

    db.commit()
    return {"ok": True}


@router.post("/skip")
def skip(
    today: Date,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Mark the ritual skipped for today — no tasks created."""
    user.last_ritual_date = today
    db.commit()
    return {"ok": True}


@router.post("/reset")
def reset(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Clear last_ritual_date so the morning wizard runs again.
    Today's tasks stay; the wizard pre-fills the existing frog."""
    user.last_ritual_date = None
    db.commit()
    return {"ok": True}
