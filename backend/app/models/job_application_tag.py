from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.base import Base


class JobApplicationTag(Base):
    __tablename__ = "job_application_tags"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tag = Column(String(64), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("JobApplication", back_populates="tag_rows")

    __table_args__ = (
        UniqueConstraint("application_id", "tag", name="uq_job_application_tags_application_id_tag"),
        Index("ix_job_application_tags_application_id_tag", "application_id", "tag"),
    )


