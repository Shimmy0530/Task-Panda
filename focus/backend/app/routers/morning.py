from datetime import date as Date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Task, User

router = APIRouter(prefix="/api/morning", tags=["morning"])


class CarryAction(BaseModel):
    task_id: int
    action: Literal["carry", "drop", "done"]


class MorningComplete(BaseModel):
    today_date: Date
    yesterday_actions: list[CarryAction] = Field(default_factory=list)
    frog_title: str = Field(min_length=1, max_length=200)
    frog_notes: str | None = None
    supporting_titles: list[str] = Field(default_factory=list)


@router.get("/state")
def morning_state(
    today: Date,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Return everything the wizard needs: yesterday's open tasks + any pre-existing frog/tasks for today."""
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
    return {
        "yesterday_open": [
            {"id": t.id, "title": t.title, "is_frog": t.is_frog, "notes": t.notes}
            for t in yest_open
        ],
        "today_existing": [
            {"id": t.id, "title": t.title, "is_frog": t.is_frog, "status": t.status}
            for t in today_tasks
        ],
        "ritual_done": user.last_ritual_date == today,
    }


@router.post("/complete")
def complete(
    payload: MorningComplete,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    today = payload.today_date
    now = datetime.utcnow()

    # 1. Process yesterday's actions
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
            # carrying forward demotes frog status — must be re-chosen for today
            task.is_frog = False
        elif ca.action == "done":
            task.status = "done"
            if not task.completed_at:
                task.completed_at = now
        elif ca.action == "drop":
            task.status = "skipped"

    db.flush()

    # 2. Frog handling — replace any existing frog for today
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
            existing_today_frog.is_frog = False  # demote, don't delete history
            db.flush()
            frog = Task(
                user_id=user.id,
                title=payload.frog_title.strip(),
                notes=payload.frog_notes,
                is_frog=True,
                day_date=today,
            )
            db.add(frog)
        # else: keep as-is
    else:
        frog = Task(
            user_id=user.id,
            title=payload.frog_title.strip(),
            notes=payload.frog_notes,
            is_frog=True,
            day_date=today,
        )
        db.add(frog)

    # 3. Supporting tasks (max 2; don't double-create if same title already there)
    today_titles = {
        t.title.lower()
        for t in db.query(Task).filter(Task.user_id == user.id, Task.day_date == today).all()
    }
    today_titles.add(payload.frog_title.strip().lower())

    added = 0
    for raw in payload.supporting_titles:
        if added >= 2:
            break
        title = (raw or "").strip()
        if not title:
            continue
        if title.lower() in today_titles:
            continue
        db.add(Task(user_id=user.id, title=title, day_date=today))
        today_titles.add(title.lower())
        added += 1

    # 4. Mark ritual done
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
