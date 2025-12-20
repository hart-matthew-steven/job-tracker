# app/models/user.py
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    # User preference: Jobs auto-refresh interval in seconds. 0 = off.
    auto_refresh_seconds = Column(Integer, nullable=False, server_default="0")
    # User preference: appearance theme (dark/light/system). UI currently uses dark, but store anyway.
    theme = Column(String(20), nullable=False, server_default="dark")
    # User preference: default job list sort mode (e.g. updated_desc/company_asc/status_asc)
    default_jobs_sort = Column(String(30), nullable=False, server_default="updated_desc")
    # User preference: default jobs "view" chip (all/active/needs_followup)
    default_jobs_view = Column(String(30), nullable=False, server_default="all")
    # User preference: data retention in days (0 = keep forever)
    data_retention_days = Column(Integer, nullable=False, server_default="0")
    password_hash = Column(String(255), nullable=False)

    is_active = Column(Boolean, nullable=False, server_default="true")
    is_email_verified = Column(Boolean, nullable=False, server_default="false")

    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ✅ user → job applications
    job_applications = relationship(
        "JobApplication",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # ✅ user → refresh tokens
    refresh_tokens = relationship(
        "RefreshToken",
        back_populates="user",
        cascade="all, delete-orphan",
    )