from datetime import date as Date, datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import Task, User
from ..schemas import TaskCreate, TaskOut, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


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


@router.post("", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    day = payload.day_date or Date.today()

    if payload.is_frog:
        existing_frog = (
            db.query(Task)
            .filter(Task.user_id == user.id, Task.day_date == day, Task.is_frog == True)  # noqa: E712
            .first()
        )
        if existing_frog:
            raise HTTPException(400, "A frog already exists for this day. Demote it first.")

    count_today = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.day_date == day)
        .count()
    )
    if count_today >= 5:
        raise HTTPException(400, "Day cap reached (5). Pick fewer, finish more.")

    task = Task(
        user_id=user.id,
        title=payload.title.strip(),
        notes=payload.notes,
        is_frog=payload.is_frog,
        day_date=day,
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

    if payload.is_frog is True and not task.is_frog:
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

    for field in ("title", "notes", "is_frog", "status"):
        v = getattr(payload, field)
        if v is not None:
            setattr(task, field, v)
    if payload.status == "done" and task.completed_at is None:
        task.completed_at = datetime.utcnow()
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
