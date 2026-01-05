from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.base import Base


class JobApplication(Base):
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True)

    # ✅ ownership
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    company_name = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)

    # Examples: applied, recruiter_screen, tech_screen, onsite, offer, rejected, withdrawn
    status = Column(String(50), nullable=False, default="applied")
    applied_date = Column(Date, nullable=True)

    job_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    last_activity_at = Column(DateTime(timezone=True), nullable=True)
    last_action_at = Column(DateTime(timezone=True), nullable=True)
    next_action_at = Column(DateTime(timezone=True), nullable=True, index=True)
    next_action_title = Column(String(255), nullable=True)
    priority = Column(String(32), nullable=False, default="normal", server_default="normal")

    # ✅ relationship back to User (optional but recommended)
    user = relationship("User", back_populates="job_applications")

    # Trackable notes (one-to-many)
    notes = relationship(
        "JobApplicationNote",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="desc(JobApplicationNote.created_at)",
    )

    documents = relationship(
        "JobDocument",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="desc(JobDocument.created_at)",
    )

    # Tags (one-to-many)
    tag_rows = relationship(
        "JobApplicationTag",
        back_populates="application",
        cascade="all, delete-orphan",
        order_by="asc(JobApplicationTag.tag)",
        lazy="selectin",
    )

    @property
    def tags(self) -> list[str]:
        rows = getattr(self, "tag_rows", None) or []
        out: list[str] = []
        for r in rows:
            t = getattr(r, "tag", None)
            if isinstance(t, str) and t:
                out.append(t)
        return out