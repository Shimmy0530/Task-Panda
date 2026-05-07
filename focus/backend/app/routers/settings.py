from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..auth import current_user
from ..db import get_db
from ..models import User

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsOut(BaseModel):
    stuck_threshold_days: int


class SettingsPatch(BaseModel):
    stuck_threshold_days: int | None = Field(default=None, ge=1, le=30)


@router.get("", response_model=SettingsOut)
def get_settings(user: User = Depends(current_user)):
    return SettingsOut(stuck_threshold_days=user.stuck_threshold_days)


@router.patch("", response_model=SettingsOut)
def patch_settings(
    payload: SettingsPatch,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if payload.stuck_threshold_days is not None:
        user.stuck_threshold_days = payload.stuck_threshold_days
    db.commit()
    return SettingsOut(stuck_threshold_days=user.stuck_threshold_days)
