from copy import deepcopy
from datetime import date as Date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Task, User
from ..schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

MAX_SUBTASKS = 25


def _enforce_day_caps(
    db: Session,
    user: User,
    target_day: Date,
    *,
    is_frog_target: bool,
    exclude_task_id: int | None = None,
):
    """Raise 400 if landing a task on target_day would break the 5/day or 1-frog/day cap."""
    q = db.query(Task).filter(Task.user_id == user.id, Task.day_date == target_day)
    if exclude_task_id is not None:
        q = q.filter(Task.id != exclude_task_id)
    rows = q.all()
    if len(rows) >= 5:
        raise HTTPException(400, "Day cap reached (5). Pick fewer, finish more.")
    if is_frog_target and any(t.is_frog for t in rows):
        raise HTTPException(400, "A frog already exists for this day. Demote it first.")


@router.get("", response_model=list[TaskOut])
def list_tasks(
    day: Date | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    day = day or Date.today()
    rows = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.day_date == day)
        .order_by(Task.is_frog.desc(), Task.created_at.asc())
        .all()
    )
    return rows


@router.get("/backlog", response_model=list[TaskOut])
def list_backlog(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.day_date.is_(None))
        .order_by(Task.created_at.desc())
        .all()
    )


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    # day_date null + non-frog ⇒ backlog. Frog must land on a real day.
    is_backlog = payload.day_date is None and not payload.is_frog
    day = None if is_backlog else (payload.day_date or Date.today())

    if day is not None:
        _enforce_day_caps(db, user, day, is_frog_target=payload.is_frog)

    task = Task(
        user_id=user.id,
        title=payload.title.strip(),
        notes=payload.notes,
        is_frog=payload.is_frog,
        day_date=day,
        effort=payload.effort,
        subtasks=[],
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/{task_id}", response_model=TaskOut)
def get_task(
    task_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "Not found")
    return task


@router.patch("/{task_id}", response_model=TaskOut)
def update_task(
    task_id: int,
    payload: TaskUpdate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "Not found")

    data = payload.model_dump(exclude_unset=True)

    if "day_date" in data:
        new_day = data["day_date"]
        if new_day is not None and new_day != task.day_date:
            _enforce_day_caps(
                db, user, new_day,
                is_frog_target=bool(data.get("is_frog", task.is_frog)),
                exclude_task_id=task.id,
            )
        task.day_date = new_day
        if new_day is None:
            task.is_frog = False  # frogs can't live in backlog
        else:
            task.carried_count = 0  # graduating from backlog resets

    if "is_frog" in data and data["is_frog"] is True and not task.is_frog:
        if task.day_date is None:
            raise HTTPException(400, "Backlog tasks can't be the frog. Pull it to today first.")
        existing_frog = (
            db.query(Task)
            .filter(
                Task.user_id == user.id,
                Task.day_date == task.day_date,
                Task.is_frog == True,  # noqa: E712
                Task.id != task.id,
            )
            .first()
        )
        if existing_frog:
            raise HTTPException(400, "Already a frog today.")

    if "subtasks" in data:
        subtasks = data["subtasks"] or []
        if len(subtasks) > MAX_SUBTASKS:
            raise HTTPException(400, f"Too many subtasks (max {MAX_SUBTASKS}).")
        task.subtasks = subtasks

    for field in ("title", "notes", "is_frog", "status", "effort", "next_action"):
        if field in data:
            setattr(task, field, data[field])

    if data.get("status") == "done" and task.completed_at is None:
        task.completed_at = datetime.utcnow()
    if data.get("status") and data["status"] != "done":
        task.completed_at = None

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "Not found")
    db.delete(task)
    db.commit()


@router.post("/{task_id}/copy", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def copy_task(
    task_id: int,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    src = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not src:
        raise HTTPException(404, "Not found")

    today = Date.today()
    _enforce_day_caps(db, user, today, is_frog_target=False)

    fresh_subtasks = [{**deepcopy(s), "done": False} for s in (src.subtasks or [])]

    dup = Task(
        user_id=user.id,
        title=src.title,
        notes=src.notes,
        is_frog=False,
        day_date=today,
        effort=src.effort,
        subtasks=fresh_subtasks,
    )
    db.add(dup)
    db.commit()
    db.refresh(dup)
    return dup


class DictationAppend(BaseModel):
    outline: str = Field(min_length=1, max_length=20000)
    transcript: str | None = None  # optional raw transcript


@router.post("/{task_id}/dictation", response_model=TaskOut)
def append_dictation(
    task_id: int,
    payload: DictationAppend,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Atomically append a timestamped dictation block to a task's notes."""
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(404, "Not found")

    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    block = f"\n\n---\n🎙 dictation · {stamp}\n\n{payload.outline.strip()}\n"
    task.notes = (task.notes or "").rstrip() + block
    db.commit()
    db.refresh(task)
    return task
