from __future__ import annotations

from enum import Enum

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text, func

from app.core.base import Base


class StripeEventStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    SKIPPED = "skipped"
    FAILED = "failed"


class StripeEvent(Base):
    __tablename__ = "stripe_events"

    id = Column(Integer, primary_key=True, index=True)
    stripe_event_id = Column(String(255), unique=True, nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(20), nullable=False, server_default=StripeEventStatus.PENDING.value)
    error_message = Column(Text, nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)


