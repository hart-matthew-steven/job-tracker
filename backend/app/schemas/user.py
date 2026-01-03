from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserMeOut(BaseModel):
    id: int
    email: str
    name: str | None = None
    auto_refresh_seconds: int
    created_at: datetime
    is_email_verified: bool
    email_verified_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserSettingsOut(BaseModel):
    auto_refresh_seconds: int
    theme: str
    default_jobs_sort: str
    default_jobs_view: str
    data_retention_days: int

    model_config = ConfigDict(from_attributes=True)


class UpdateSettingsIn(BaseModel):
    auto_refresh_seconds: int = Field(ge=0, le=60)
    theme: str = Field(default="dark", max_length=20)
    default_jobs_sort: str = Field(default="updated_desc", max_length=30)
    default_jobs_view: str = Field(default="all", max_length=30)
    data_retention_days: int = Field(default=0, ge=0, le=3650)


