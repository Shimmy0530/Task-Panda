from datetime import date as Date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..llm import first_action, subtasks_from_task, weekly_review
from ..models import Capture, Session as FocusSession, Task, User
from ..schemas import (
    CaptureConvertRequest,
    CaptureConvertResponse,
    CaptureCreate,
    CaptureOut,
    FirstActionRequest,
    FirstActionResponse,
    SubtaskItem,
)
from .tasks import _enforce_day_caps

capture_router = APIRouter(prefix="/api/capture", tags=["capture"])
llm_router = APIRouter(prefix="/api/llm", tags=["llm"])


@capture_router.post("", response_model=CaptureOut, status_code=201)
def create_capture(
    payload: CaptureCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    c = Capture(user_id=user.id, content=payload.content.strip())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@capture_router.get("", response_model=list[CaptureOut])
def list_captures(
    processed: bool | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Capture).filter(Capture.user_id == user.id)
    if processed is not None:
        q = q.filter(Capture.processed == processed)
    return q.order_by(Capture.created_at.desc()).limit(200).all()


@capture_router.patch("/{cap_id}", response_model=CaptureOut)
def mark_processed(
    cap_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    c = db.query(Capture).filter(Capture.id == cap_id, Capture.user_id == user.id).first()
    if not c:
        raise HTTPException(404, "Not found")
    c.processed = True
    db.commit()
    db.refresh(c)
    return c


@capture_router.post("/{cap_id}/convert", response_model=CaptureConvertResponse)
def convert_capture(
    cap_id: int,
    payload: CaptureConvertRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    capture = (
        db.query(Capture)
        .filter(Capture.id == cap_id, Capture.user_id == user.id)
        .first()
    )
    if not capture:
        raise HTTPException(404, "Not found")
    if capture.processed:
        raise HTTPException(409, "Already processed")

    target_day = Date.today() if payload.target == "today" else None
    if target_day is not None:
        _enforce_day_caps(db, user, target_day, is_frog_target=False)

    content = capture.content.strip()
    title = content[:200]
    notes = content if len(content) > 200 else None

    task = Task(
        user_id=user.id,
        title=title,
        notes=notes,
        is_frog=False,
        day_date=target_day,
        subtasks=[],
    )
    db.add(task)
    capture.processed = True
    db.commit()
    db.refresh(task)
    db.refresh(capture)
    return {"task": task, "capture": capture}


@llm_router.post("/first-action", response_model=FirstActionResponse)
async def first_action_endpoint(
    payload: FirstActionRequest,
    user: User = Depends(current_user),
):
    try:
        action = await first_action(payload.title, payload.notes)
    except Exception as e:
        raise HTTPException(503, f"LLM unavailable: {e}")
    return FirstActionResponse(action=action)


class SubtasksRequest(BaseModel):
    task_id: int


class SubtasksResponse(BaseModel):
    subtasks: list[SubtaskItem]


@llm_router.post("/subtasks", response_model=SubtasksResponse)
async def subtasks_endpoint(
    payload: SubtasksRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == payload.task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "Not found")
    try:
        items = await subtasks_from_task(task.title, task.notes)
    except Exception as e:
        raise HTTPException(503, f"LLM unavailable: {e}")
    if items is None:
        raise HTTPException(503, "AI didn't return a parseable list. Try again.")
    return SubtasksResponse(
        subtasks=[SubtaskItem(id=uuid4().hex, title=s, done=False) for s in items]
    )


# Module-level cache: key = (user_id, isoformat date), val = (summary, generated_at).
_WEEKLY_CACHE: dict[tuple[int, str], tuple[str, datetime]] = {}


class WeeklyReviewResponse(BaseModel):
    summary: str
    generated_at: datetime


@llm_router.post("/weekly-review", response_model=WeeklyReviewResponse)
async def weekly_review_endpoint(
    today: Date,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    cache_key = (user.id, today.isoformat())
    cached = _WEEKLY_CACHE.get(cache_key)
    if cached:
        summary, generated_at = cached
        return WeeklyReviewResponse(summary=summary, generated_at=generated_at)

    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    sessions = (
        db.query(FocusSession)
        .filter(FocusSession.user_id == user.id, FocusSession.started_at >= week_start)
        .all()
    )
    total_seconds = 0
    frog_seconds = 0
    for s in sessions:
        end = s.ended_at or datetime.utcnow()
        secs = int((end - s.started_at).total_seconds())
        total_seconds += secs
        t = db.get(Task, s.task_id)
        if t and t.is_frog:
            frog_seconds += secs

    completed = (
        db.query(Task)
        .filter(
            Task.user_id == user.id,
            Task.completed_at.isnot(None),
            Task.completed_at >= week_start,
        )
        .all()
    )
    carried = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.carried_count > 0)
        .order_by(Task.carried_count.desc())
        .limit(15)
        .all()
    )

    events = {
        "total_focused_seconds": total_seconds,
        "frog_focused_seconds": frog_seconds,
        "completed_tasks": [
            {"title": t.title, "is_frog": t.is_frog} for t in completed
        ],
        "still_carrying": [
            {"title": t.title, "carried_count": t.carried_count} for t in carried
        ],
    }

    try:
        summary = await weekly_review(events)
    except Exception as e:
        raise HTTPException(503, f"LLM unavailable: {e}")

    # Don't cache degenerate output (refusals, empty strings, missing structure).
    if not summary or not summary.strip() or "## " not in summary:
        raise HTTPException(503, "AI returned an unusable summary. Try again.")

    now = datetime.utcnow()
    _WEEKLY_CACHE[cache_key] = (summary, now)
    return WeeklyReviewResponse(summary=summary, generated_at=now)
