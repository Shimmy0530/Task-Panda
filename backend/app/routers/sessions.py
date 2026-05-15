import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from ..auth import current_user
from ..db import get_db
from ..models import Session, Task, User
from ..schemas import SessionOut, SessionStart
from .tasks import _visible_tasks

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


@router.post("/start", response_model=SessionOut)
def start_session(
    payload: SessionStart,
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    task = (
        _visible_tasks(db.query(Task))
        .filter(Task.id == payload.task_id, Task.user_id == user.id)
        .first()
    )
    if not task:
        raise HTTPException(404, "Task not found")

    open_session = (
        db.query(Session)
        .filter(Session.user_id == user.id, Session.ended_at.is_(None))
        .first()
    )
    if open_session:
        raise HTTPException(400, "Another session is already running.")

    s = Session(
        task_id=task.id,
        user_id=user.id,
        duration_planned_seconds=max(60, min(payload.duration_planned_seconds, 7200)),
    )
    task.status = "active"
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.post("/{session_id}/end", response_model=SessionOut)
def end_session(
    session_id: int,
    completed: bool = True,
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    s = db.query(Session).filter(Session.id == session_id, Session.user_id == user.id).first()
    if not s:
        raise HTTPException(404, "Not found")
    if s.ended_at:
        return s
    s.ended_at = datetime.utcnow()
    s.completed = completed
    if s.task and s.task.status == "active":
        s.task.status = "pending"
    db.commit()
    db.refresh(s)
    return s


@router.get("/today")
def today_summary(
    start: datetime,
    end: datetime,
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    start = _to_naive_utc(start)
    end = _to_naive_utc(end)
    rows = (
        db.query(Session)
        .filter(Session.user_id == user.id, Session.started_at >= start, Session.started_at < end)
        .all()
    )

    total_seconds = 0
    frog_seconds = 0
    for r in rows:
        end = r.ended_at or datetime.utcnow()
        secs = int((end - r.started_at).total_seconds())
        total_seconds += secs
        task = db.get(Task, r.task_id)
        if task and task.deleted_at is None and task.is_frog:
            frog_seconds += secs

    return {
        "sessions": len(rows),
        "total_seconds": total_seconds,
        "frog_seconds": frog_seconds,
        "frog_ratio": (frog_seconds / total_seconds) if total_seconds else 0.0,
    }


@router.get("/week")
def week_summary(
    ranges: str,
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    """Per-day frog-vs-other ratio for the last 7 days."""
    out = []
    try:
        parsed_ranges = json.loads(ranges)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid day ranges")

    if not isinstance(parsed_ranges, list) or len(parsed_ranges) != 7:
        raise HTTPException(400, "Expected 7 day ranges")

    for item in parsed_ranges:
        try:
            day = item["day"]
            start = _to_naive_utc(datetime.fromisoformat(item["start"].replace("Z", "+00:00")))
            end = _to_naive_utc(datetime.fromisoformat(item["end"].replace("Z", "+00:00")))
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Invalid day range")
        rows = (
            db.query(Session)
            .filter(Session.user_id == user.id, Session.started_at >= start, Session.started_at < end)
            .all()
        )
        total = frog = 0
        for r in rows:
            te = r.ended_at or datetime.utcnow()
            secs = int((te - r.started_at).total_seconds())
            total += secs
            task = db.get(Task, r.task_id)
            if task and task.deleted_at is None and task.is_frog:
                frog += secs
        out.append({
            "day": day,
            "total_seconds": total,
            "frog_seconds": frog,
        })
    return out
