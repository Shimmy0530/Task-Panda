import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import (
    current_user,
    equalize_login_timing,
    hash_password,
    issue_jwt,
    revoke_user_sessions,
    slow_fail,
    user_dict,
    verify_user_password,
    verify_user_totp,
)
from ..clock import utcnow
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
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Pending TOTP secrets keyed by user.id; lives only in this process.
# Cleared on confirm or app restart. Single-replica SQLite deploy = fine.
_PENDING_TOTP: dict[int, str] = {}

# Open-registration abuse controls (in-process, single-replica — same model as
# _PENDING_TOTP). A per-IP fixed window slows automated flooding; a global cap
# bounds how many unapproved rows can pile up in the users table at once.
_REGISTER_ATTEMPTS: dict[str, list[datetime]] = {}
_REGISTER_WINDOW = timedelta(hours=1)
_REGISTER_MAX_PER_WINDOW = 5
_MAX_PENDING_ACCOUNTS = 25


def _client_key(request: Request) -> str:
    """Identify the caller for rate limiting. Behind nginx, X-Real-IP carries
    the real client IP (Cloudflare-restored upstream); fall back to the socket
    peer for direct/local connections."""
    return request.headers.get("x-real-ip") or (
        request.client.host if request.client else "unknown"
    )


def _register_rate_limited(key: str, now: datetime) -> bool:
    """Fixed-window per-IP limiter. Prunes expired hits on access and records
    this attempt when under the cap."""
    hits = [t for t in _REGISTER_ATTEMPTS.get(key, []) if now - t < _REGISTER_WINDOW]
    if len(hits) >= _REGISTER_MAX_PER_WINDOW:
        _REGISTER_ATTEMPTS[key] = hits
        return True
    hits.append(now)
    _REGISTER_ATTEMPTS[key] = hits
    return False

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
        approved_at=utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already complete")
    db.refresh(user)
    _set_session_cookie(response, issue_jwt(user))
    return {"ok": True, "user": user_dict(user)}


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Open registration. Account is created in pending state and cannot
    sign in until an admin approves it. Refused on a fresh install — the
    very first account must come through /setup so there's an admin to
    approve subsequent registrations."""
    now = utcnow()
    if _register_rate_limited(_client_key(request), now):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many registration attempts. Try again later.",
        )
    if db.query(User).count() == 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "First account must be created through setup.",
        )
    pending = (
        db.query(User)
        .filter(User.approved_at.is_(None), User.disabled_at.is_(None))
        .count()
    )
    if pending >= _MAX_PENDING_ACCOUNTS:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many pending registrations awaiting approval. Try again later.",
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

    _set_session_cookie(response, issue_jwt(user))
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
    user.welcomed_at = utcnow()
    db.commit()


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not verify_user_password(user, payload.current_password):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password incorrect")
    user.password_hash = hash_password(payload.new_password)
    revoke_user_sessions(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, issue_jwt(user))
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
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    pending = _PENDING_TOTP.get(user.id)
    if not pending:
        raise HTTPException(400, "No pending TOTP setup. Start over.")
    if not pyotp.TOTP(pending).verify(payload.code, valid_window=1):
        raise HTTPException(400, "Code didn't match. Try again.")
    user.totp_secret = pending
    revoke_user_sessions(user)
    _PENDING_TOTP.pop(user.id, None)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, issue_jwt(user))
    return {"ok": True}


@router.post("/totp/disable")
async def totp_disable(
    payload: TotpDisableRequest,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    if not user.totp_secret:
        raise HTTPException(400, "TOTP not enrolled.")
    if not verify_user_password(user, payload.password):
        await slow_fail()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password incorrect")
    user.totp_secret = None
    revoke_user_sessions(user)
    db.commit()
    db.refresh(user)
    _set_session_cookie(response, issue_jwt(user))
    return {"ok": True}
