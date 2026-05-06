from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..auth import (
    current_user,
    issue_jwt,
    slow_fail,
    totp_enabled,
    verify_password,
    verify_totp,
)
from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config():
    """Public — tells the login UI whether to show the TOTP field."""
    return {"totp_required": totp_enabled()}


@router.post("/login")
async def login(payload: LoginRequest, response: Response):
    if not verify_password(payload.password):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")

    if totp_enabled():
        if not verify_totp(payload.totp_code or ""):
            await slow_fail()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")

    token = issue_jwt()
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {
        "id": user.id,
        "last_ritual_date": user.last_ritual_date.isoformat() if user.last_ritual_date else None,
    }
