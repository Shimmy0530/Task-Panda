from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin, revoke_user_sessions
from ..db import get_db
from ..models import User
from ..schemas import AdminCreateUserRequest, AdminResetPasswordRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _to_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "totp_enrolled": bool(user.totp_secret),
        "disabled_at": user.disabled_at.isoformat() if user.disabled_at else None,
        "approved_at": user.approved_at.isoformat() if user.approved_at else None,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.get("/users")
def list_users(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    rows = db.query(User).order_by(User.id.asc()).all()
    return [_to_out(u) for u in rows]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: AdminCreateUserRequest,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_admin=payload.is_admin,
        approved_at=datetime.utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists")
    db.refresh(user)
    return _to_out(user)


@router.post("/users/{user_id}/approve")
def approve_user(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    if user.approved_at is None:
        user.approved_at = datetime.utcnow()
        db.commit()
    return _to_out(user)


@router.post("/users/{user_id}/reset-password")
def reset_password(
    user_id: int,
    payload: AdminResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(400, "Use change-password to update your own password.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    if user.is_admin:
        raise HTTPException(403, "Can't reset another admin's password — they change their own.")
    user.password_hash = hash_password(payload.new_password)
    revoke_user_sessions(user)
    db.commit()
    return {"ok": True}


@router.post("/users/{user_id}/disable")
def disable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if user_id == admin.id:
        raise HTTPException(400, "You can't disable your own account.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    if user.disabled_at is None:
        user.disabled_at = datetime.utcnow()
        revoke_user_sessions(user)
        db.commit()
    return _to_out(user)


@router.post("/users/{user_id}/enable")
def enable_user(
    user_id: int,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Not found")
    user.disabled_at = None
    db.commit()
    return _to_out(user)
