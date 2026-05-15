import asyncio
import secrets
from datetime import datetime, timedelta

import bcrypt
import pyotp
from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .db import get_db
from .models import User

JWT_ALG = "HS256"
JWT_TTL_DAYS = 30

# Real bcrypt hash used to equalize timing when login is attempted with an
# unknown username — keeps the response time roughly constant whether or not
# the user exists. Computed once at module import.
_TIMING_DUMMY_HASH = bcrypt.hashpw(b"prevent-username-enum", bcrypt.gensalt(12)).decode("utf-8")


def equalize_login_timing(plaintext: str) -> None:
    """Run a throwaway bcrypt verify against a fixed dummy hash."""
    try:
        bcrypt.checkpw(plaintext.encode("utf-8"), _TIMING_DUMMY_HASH.encode("utf-8"))
    except (ValueError, TypeError):
        pass


def issue_jwt(user: User) -> str:
    payload = {
        "sub": str(user.id),
        "sv": user.session_version,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=JWT_TTL_DAYS),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALG)


def decode_jwt(token: str) -> tuple[int, int]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALG])
        return int(payload["sub"]), int(payload["sv"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")


def current_user(
    session: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id, token_session_version = decode_jwt(session)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    if user.disabled_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account disabled")
    if token_session_version != user.session_version:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")
    if user.approved_at is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account pending approval")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin only")
    return user


def revoke_user_sessions(user: User) -> None:
    user.session_version = (user.session_version or 0) + 1


def user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "totp_enrolled": bool(user.totp_secret),
        "last_ritual_date": user.last_ritual_date.isoformat() if user.last_ritual_date else None,
        "welcomed_at": user.welcomed_at.isoformat() if user.welcomed_at else None,
    }


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")


def verify_user_password(user: User, plaintext: str) -> bool:
    if not user.password_hash:
        return False
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), user.password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def verify_user_totp(user: User, code: str | None) -> bool:
    if not user.totp_secret:
        return True  # not enrolled; treated as pass
    if not code or not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(user.totp_secret).verify(code, valid_window=1)


async def slow_fail():
    """Constant-ish ~1.2s delay on auth failures to slow brute force."""
    await asyncio.sleep(1.2)
