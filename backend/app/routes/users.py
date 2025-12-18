from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import hash_password, verify_password
from app.dependencies.auth import get_current_user
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.user import ChangePasswordIn, UpdateSettingsIn, UserMeOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeOut)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.get("/me/settings", response_model=UserMeOut)
def get_my_settings(user: User = Depends(get_current_user)) -> User:
    # Reuse UserMeOut for now (small schema, includes auto_refresh_seconds).
    return user


@router.put("/me/settings", response_model=MessageOut)
def update_my_settings(
    payload: UpdateSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.auto_refresh_seconds = int(payload.auto_refresh_seconds or 0)
    db.add(user)
    db.commit()
    return {"message": "Settings updated"}


@router.post("/me/change-password", response_model=MessageOut)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    if payload.current_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password",
        )

    # Update password hash
    user.password_hash = hash_password(payload.new_password)
    db.add(user)

    # Revoke all refresh tokens (forces re-login everywhere)
    now = datetime.now(timezone.utc)
    (
        db.query(RefreshToken)
        .filter(RefreshToken.user_id == user.id)
        .filter(RefreshToken.revoked_at.is_(None))
        .update({RefreshToken.revoked_at: now}, synchronize_session=False)
    )

    db.commit()

    return {"message": "Password updated. Please log in again."}


