from datetime import datetime, date
from typing import Literal
from pydantic import BaseModel, Field, model_validator


EffortLevel = Literal["S", "M", "L"]


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = None


class SubtaskItem(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    done: bool = False


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    is_frog: bool = False
    day_date: date | None = None  # None = backlog (unless is_frog)
    effort: EffortLevel | None = None

    @model_validator(mode="after")
    def _frog_must_have_day(self):
        if self.is_frog and self.day_date is None:
            raise ValueError("Frogs must land on a real day; backlog is for non-frog tasks.")
        return self


class TaskUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    is_frog: bool | None = None
    status: str | None = None
    day_date: date | None = None  # explicit null = demote to backlog
    effort: EffortLevel | None = None
    subtasks: list[SubtaskItem] | None = None  # full-list replace

    @model_validator(mode="after")
    def _no_frog_in_backlog(self):
        # Same PATCH cannot promote to frog while demoting to backlog.
        if (
            self.is_frog is True
            and "day_date" in self.model_fields_set
            and self.day_date is None
        ):
            raise ValueError("Cannot set is_frog=True and day_date=null in the same patch.")
        return self


class TaskOut(BaseModel):
    id: int
    title: str
    notes: str | None
    is_frog: bool
    status: str
    day_date: date | None
    created_at: datetime
    completed_at: datetime | None
    subtasks: list[SubtaskItem]
    effort: EffortLevel | None
    carried_count: int

    class Config:
        from_attributes = True


class SessionStart(BaseModel):
    task_id: int
    duration_planned_seconds: int = 1500


class SessionOut(BaseModel):
    id: int
    task_id: int
    duration_planned_seconds: int
    started_at: datetime
    ended_at: datetime | None
    completed: bool

    class Config:
        from_attributes = True


class CaptureCreate(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class CaptureOut(BaseModel):
    id: int
    content: str
    processed: bool
    created_at: datetime

    class Config:
        from_attributes = True


class FirstActionRequest(BaseModel):
    title: str
    notes: str | None = None


class FirstActionResponse(BaseModel):
    action: str
