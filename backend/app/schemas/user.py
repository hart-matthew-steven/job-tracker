from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class UserMeOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    auto_refresh_seconds: int
    is_email_verified: bool
    created_at: datetime
    email_verified_at: datetime | None = None

    class Config:
        from_attributes = True


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UpdateSettingsIn(BaseModel):
    auto_refresh_seconds: int = Field(ge=0, le=60)


