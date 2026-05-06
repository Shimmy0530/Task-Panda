from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..llm import first_action
from ..models import Capture, User
from ..schemas import (
    CaptureCreate,
    CaptureOut,
    FirstActionRequest,
    FirstActionResponse,
)

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
