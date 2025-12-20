from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

from app.core.base import Base


class JobActivity(Base):
    __tablename__ = "job_activities"

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

    # e.g. status_changed, tags_updated, note_added, note_deleted, document_uploaded, document_deleted
    type = Column(String(50), nullable=False, index=True)

    message = Column(String(255), nullable=True)
    data = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("JobApplication")
    user = relationship("User")


