from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.common import MessageOut
from app.schemas.user import UpdateSettingsIn, UserMeOut, UserSettingsOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserMeOut)
def get_me(user: User = Depends(get_current_user)) -> UserMeOut:
    return UserMeOut(
        id=user.id,
        email=user.email,
        name=user.name,
        auto_refresh_seconds=user.auto_refresh_seconds,
        created_at=user.created_at,
        is_email_verified=getattr(user, "is_email_verified", False),
        email_verified_at=getattr(user, "email_verified_at", None),
    )


@router.get("/me/settings", response_model=UserSettingsOut)
def get_my_settings(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me/settings", response_model=MessageOut)
def update_my_settings(
    payload: UpdateSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    user.auto_refresh_seconds = int(payload.auto_refresh_seconds or 0)
    user.theme = (payload.theme or "dark").strip().lower() or "dark"
    user.default_jobs_sort = (payload.default_jobs_sort or "updated_desc").strip() or "updated_desc"
    user.default_jobs_view = (payload.default_jobs_view or "all").strip().lower() or "all"
    user.data_retention_days = int(payload.data_retention_days or 0)
    db.add(user)
    db.commit()
    return {"message": "Settings updated"}


