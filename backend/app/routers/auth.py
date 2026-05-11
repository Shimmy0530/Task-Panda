import pyotp
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    current_user,
    equalize_login_timing,
    hash_password,
    issue_jwt,
    slow_fail,
    user_dict,
    verify_user_password,
    verify_user_totp,
)
from ..config import settings
from ..db import get_db
from ..models import User
from ..schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    SetupRequest,
    TotpConfirmRequest,
    TotpDisableRequest,
)
from datetime import datetime

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Pending TOTP secrets keyed by user.id; lives only in this process.
# Cleared on confirm or app restart. Single-replica SQLite deploy = fine.
_PENDING_TOTP: dict[int, str] = {}

_COOKIE_KW = dict(
    httponly=True,
    secure=True,
    samesite="lax",
    max_age=60 * 60 * 24 * 30,
    path="/",
)


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(key=settings.SESSION_COOKIE_NAME, value=token, **_COOKIE_KW)


@router.get("/setup-required")
def setup_required(db: Session = Depends(get_db)):
    """Public — true when no users exist yet, prompting the first-run signup UI."""
    return {"setup_required": db.query(User).count() == 0}


@router.post("/setup")
def setup(payload: SetupRequest, response: Response, db: Session = Depends(get_db)):
    """First-run admin signup. Only succeeds when the users table is empty."""
    if db.query(User).count() > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already complete")
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=True,
        approved_at=datetime.utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already complete")
    db.refresh(user)
    _set_session_cookie(response, issue_jwt(user.id))
    return {"ok": True, "user": user_dict(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Open registration. Account is created in pending state and cannot
    sign in until an admin approves it. Refused on a fresh install — the
    very first account must come through /setup so there's an admin to
    approve subsequent registrations."""
    if db.query(User).count() == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "First account must be created through setup.",
        )
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=False,
        approved_at=None,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    return {"ok": True, "pending": True}


@router.post("/login")
async def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        equalize_login_timing(payload.password)
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    if not verify_user_password(user, payload.password) or user.disabled_at is not None:
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    if not verify_user_totp(user, payload.totp_code):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bad credentials")
    if user.approved_at is None:
        # Password checks out, but the account hasn't been approved by an
        # admin yet. Tell the user plainly — registration already reveals
        # which usernames exist, so this leaks nothing new.
        await slow_fail()
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Account pending admin approval.",
        )

    _set_session_cookie(response, issue_jwt(user.id))
    return {"ok": True, "user": user_dict(user)}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(current_user)):
    return user_dict(user)


@router.post("/welcome", status_code=status.HTTP_204_NO_CONTENT)
def mark_welcomed(
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    """Stamp the current user as having seen the welcome tour.
    Idempotent: calling again just refreshes the timestamp."""
    user.welcomed_at = datetime.utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_user_password(user, payload.current_password):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password incorrect")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


@router.post("/totp/setup")
def totp_setup(user: User = Depends(current_user)):
    if user.totp_secret:
        raise HTTPException(400, "TOTP already enrolled. Disable it first.")
    secret = pyotp.random_base32()
    _PENDING_TOTP[user.id] = secret
    uri = pyotp.totp.TOTP(secret).provisioning_uri(
        name=user.username or f"user-{user.id}",
        issuer_name="Task Panda",
    )
    return {"secret": secret, "uri": uri}


@router.post("/totp/confirm")
def totp_confirm(
    payload: TotpConfirmRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    pending = _PENDING_TOTP.get(user.id)
    if not pending:
        raise HTTPException(400, "No pending TOTP setup. Start over.")
    if not pyotp.TOTP(pending).verify(payload.code, valid_window=1):
        raise HTTPException(400, "Code didn't match. Try again.")
    user.totp_secret = pending
    _PENDING_TOTP.pop(user.id, None)
    db.commit()
    return {"ok": True}


@router.post("/totp/disable")
async def totp_disable(
    payload: TotpDisableRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not user.totp_secret:
        raise HTTPException(400, "TOTP not enrolled.")
    if not verify_user_password(user, payload.password):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password incorrect")
    user.totp_secret = None
    db.commit()
    return {"ok": True}
