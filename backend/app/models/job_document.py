from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, BigInteger, func
from sqlalchemy.orm import relationship
from app.core.base import Base

class JobDocument(Base):
    __tablename__ = "job_documents"

    id = Column(Integer, primary_key=True, index=True)

    application_id = Column(
        Integer,
        ForeignKey("job_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    doc_type = Column(String(50), nullable=False, index=True)

    s3_key = Column(String(512), nullable=False, unique=True, index=True)
    original_filename = Column(String(512), nullable=False)
    content_type = Column(String(255), nullable=True)
    size_bytes = Column(BigInteger, nullable=True)

    # NEW
    status = Column(
        String(20),
        nullable=False,
        server_default="pending",
    )
    uploaded_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    application = relationship("JobApplication", back_populates="documents")