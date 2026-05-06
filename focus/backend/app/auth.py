import asyncio
import secrets
from datetime import datetime, timedelta

import bcrypt
import pyotp
from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from .config import settings
from .db import OWNER_ID, get_db
from .models import User

JWT_ALG = "HS256"
JWT_TTL_DAYS = 30


def issue_jwt() -> str:
    payload = {
        "sub": str(OWNER_ID),
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(days=JWT_TTL_DAYS),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALG)


def decode_jwt(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALG])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session")


def current_user(
    session: str | None = Cookie(default=None, alias=settings.SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_jwt(session)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


def verify_password(plaintext: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode("utf-8"), settings.AUTH_PASSWORD_HASH.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def totp_enabled() -> bool:
    return bool(settings.AUTH_TOTP_SECRET.strip())


def verify_totp(code: str) -> bool:
    if not totp_enabled():
        return True  # not configured; treated as pass
    if not code or not code.isdigit() or len(code) != 6:
        return False
    return pyotp.TOTP(settings.AUTH_TOTP_SECRET).verify(code, valid_window=1)


async def slow_fail():
    """Constant-ish ~1.2s delay on auth failures to slow brute force."""
    await asyncio.sleep(1.2)
