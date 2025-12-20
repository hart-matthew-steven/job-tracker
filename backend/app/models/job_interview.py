from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.base import Base


class JobInterview(Base):
    __tablename__ = "job_interviews"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # e.g. recruiter_screen, tech_screen, onsite, final
    stage = Column(String(50), nullable=True)
    # e.g. phone, video, onsite
    kind = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)  # address or URL
    interviewer = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, server_default="scheduled")  # scheduled|completed|cancelled

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    application = relationship("JobApplication")
    user = relationship("User")


