# app/models/user.py
"""User model for Cognito-backed authentication."""
from sqlalchemy import Boolean, Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    # --- Identity fields ---
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)

    cognito_sub = Column(String(255), unique=True, index=True, nullable=False)
    auth_provider = Column(String(20), nullable=False, server_default="cognito")

    # --- User preferences ---
    # Jobs auto-refresh interval in seconds. 0 = off.
    auto_refresh_seconds = Column(Integer, nullable=False, server_default="0")
    # Appearance theme (dark/light/system). UI currently uses dark, but store anyway.
    theme = Column(String(20), nullable=False, server_default="dark")
    # Default job list sort mode (e.g. updated_desc/company_asc/status_asc)
    default_jobs_sort = Column(String(30), nullable=False, server_default="updated_desc")
    # Default jobs "view" chip (all/active/needs_followup)
    default_jobs_view = Column(String(30), nullable=False, server_default="all")
    # Data retention in days (0 = keep forever)
    data_retention_days = Column(Integer, nullable=False, server_default="0")

    # --- Status flags ---
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # ✅ user → job applications
    job_applications = relationship(
        "JobApplication",
        back_populates="user",
        cascade="all, delete-orphan",
    )
