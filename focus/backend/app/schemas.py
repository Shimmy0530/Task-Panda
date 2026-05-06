from datetime import datetime, date
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str = Field(min_length=1, max_length=200)
    totp_code: str | None = None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    notes: str | None = None
    is_frog: bool = False
    day_date: date | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    notes: str | None = None
    is_frog: bool | None = None
    status: str | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    notes: str | None
    is_frog: bool
    status: str
    day_date: date
    created_at: datetime
    completed_at: datetime | None

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
