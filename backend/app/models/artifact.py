from __future__ import annotations

from datetime import datetime

from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON, TypeDecorator

from app.core.base import Base


class ArtifactType(str, PyEnum):
    resume = "resume"
    job_description = "job_description"
    note = "note"


class ArtifactSourceType(str, PyEnum):
    upload = "upload"
    url = "url"
    paste = "paste"


class ArtifactStatus(str, PyEnum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class JSONBCompat(TypeDecorator):
    impl = JSONB
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB(astext_type=Text()))
        return dialect.type_descriptor(JSON())


class AIArtifact(Base):
    __tablename__ = "ai_artifacts"
    __table_args__ = (
        UniqueConstraint("user_id", "artifact_type", "version_number", name="uq_artifact_version"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    artifact_type = Column(SAEnum(ArtifactType), nullable=False)
    source_type = Column(SAEnum(ArtifactSourceType), nullable=False)
    source_details = Column(JSONBCompat(), nullable=True)
    s3_key = Column(String(512), nullable=True)
    text_content = Column(Text, nullable=True)
    status = Column(SAEnum(ArtifactStatus), nullable=False, default=ArtifactStatus.pending)
    failure_reason = Column(Text, nullable=True)
    version_number = Column(Integer, nullable=False, default=1)
    previous_version_id = Column(Integer, ForeignKey("ai_artifacts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="artifacts")
    conversation = relationship("AIConversation", back_populates="artifacts")
    previous_version = relationship("AIArtifact", remote_side=[id], uselist=False)
    conversation_links = relationship("AIConversationArtifact", back_populates="artifact", cascade="all, delete-orphan")


class AIConversationArtifact(Base):
    __tablename__ = "ai_conversation_artifacts"
    __table_args__ = (UniqueConstraint("conversation_id", "role", name="uq_conversation_role"),)

    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    artifact_id = Column(Integer, ForeignKey("ai_artifacts.id", ondelete="CASCADE"), nullable=False)
    role = Column(SAEnum(ArtifactType), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    pinned_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("AIConversation", back_populates="artifact_links")
    artifact = relationship("AIArtifact", back_populates="conversation_links")

