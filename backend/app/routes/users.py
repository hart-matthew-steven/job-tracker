from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.common import MessageOut
from app.schemas.user import (
    UpdateSettingsIn,
    UpdateUiPreferencesIn,
    UiPreferencesOut,
    UserMeOut,
    UserSettingsOut,
)

router = APIRouter(prefix="/users", tags=["users"])

UI_PREFERENCE_KEYS = {
    "job_details_notes_collapsed",
    "job_details_interviews_collapsed",
    "job_details_timeline_collapsed",
    "job_details_documents_collapsed",
    "nav_expanded",
}

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
        ui_preferences=(getattr(user, "ui_preferences", None) or {}) if hasattr(user, "ui_preferences") else {},
    )


@router.get("/me/settings", response_model=UserSettingsOut)
def get_my_settings(user: User = Depends(get_current_user)) -> User:
    return user


def _load_user_in_session(db: Session, user: User) -> User:
    db_user = db.get(User, user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user


@router.put("/me/settings", response_model=MessageOut)
def update_my_settings(
    payload: UpdateSettingsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    db_user = _load_user_in_session(db, user)
    db_user.auto_refresh_seconds = int(payload.auto_refresh_seconds or 0)
    db_user.theme = (payload.theme or "dark").strip().lower() or "dark"
    db_user.default_jobs_sort = (payload.default_jobs_sort or "updated_desc").strip() or "updated_desc"
    db_user.default_jobs_view = (payload.default_jobs_view or "all").strip().lower() or "all"
    db_user.data_retention_days = int(payload.data_retention_days or 0)
    db.commit()
    return {"message": "Settings updated"}


@router.patch("/me/ui-preferences", response_model=UiPreferencesOut)
def update_ui_preferences(
    payload: UpdateUiPreferencesIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UiPreferencesOut:
    db_user = _load_user_in_session(db, user)
    prefs = dict(getattr(db_user, "ui_preferences", {}) or {})
    for key, value in payload.preferences.items():
        if key not in UI_PREFERENCE_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown preference key: {key}")
        prefs[key] = bool(value)

    db_user.ui_preferences = prefs
    db.commit()
    db.refresh(db_user)
    return UiPreferencesOut(ui_preferences=prefs)


