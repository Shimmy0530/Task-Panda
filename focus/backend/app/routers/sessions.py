from datetime import datetime, date as Date, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session as OrmSession

from ..auth import current_user
from ..db import get_db
from ..models import Session, Task, User
from ..schemas import SessionOut, SessionStart

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("/start", response_model=SessionOut)
def start_session(
    payload: SessionStart,
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == payload.task_id, Task.user_id == user.id).first()
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
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    today = Date.today()
    start = datetime.combine(today, datetime.min.time())

    rows = (
        db.query(Session)
        .filter(Session.user_id == user.id, Session.started_at >= start)
        .all()
    )

    total_seconds = 0
    frog_seconds = 0
    for r in rows:
        end = r.ended_at or datetime.utcnow()
        secs = int((end - r.started_at).total_seconds())
        total_seconds += secs
        task = db.get(Task, r.task_id)
        if task and task.is_frog:
            frog_seconds += secs

    return {
        "sessions": len(rows),
        "total_seconds": total_seconds,
        "frog_seconds": frog_seconds,
        "frog_ratio": (frog_seconds / total_seconds) if total_seconds else 0.0,
    }


@router.get("/week")
def week_summary(
    user: User = Depends(current_user),
    db: OrmSession = Depends(get_db),
):
    """Per-day frog-vs-other ratio for the last 7 days."""
    today = Date.today()
    out = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        start = datetime.combine(d, datetime.min.time())
        end = start + timedelta(days=1)
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
            if task and task.is_frog:
                frog += secs
        out.append({
            "day": d.isoformat(),
            "total_seconds": total,
            "frog_seconds": frog,
        })
    return out
