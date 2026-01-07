from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.base import Base


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source = Column(String(50), nullable=False)
    source_ref = Column(String(255), nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(10), nullable=False, server_default="usd")
    description = Column(Text, nullable=True)
    pack_key = Column(String(50), nullable=True)
    stripe_checkout_session_id = Column(String(255), nullable=True, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), nullable=False)
    entry_type = Column(String(50), nullable=False, server_default="credit_purchase")
    status = Column(String(20), nullable=False, server_default="posted")
    correlation_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", backref="credit_ledger_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "source_ref", name="uq_credit_ledger_user_source_ref"),
        UniqueConstraint("user_id", "idempotency_key", name="uq_credit_ledger_user_idempotency"),
    )


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature = Column(String(100), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_tokens = Column(Integer, nullable=False, server_default="0", default=0)
    completion_tokens = Column(Integer, nullable=False, server_default="0", default=0)
    total_tokens = Column(Integer, nullable=False, server_default="0", default=0)
    cost_cents = Column(Integer, nullable=False)
    request_id = Column(String(255), nullable=True)
    reserved_cents = Column(Integer, nullable=False, server_default="0", default=0)
    actual_cents = Column(Integer, nullable=False, server_default="0", default=0)
    status = Column(String(20), nullable=False, server_default="pending")
    response_text = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    user = relationship("User", backref="ai_usage_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "request_id", name="uq_ai_usage_user_request_id"),
    )


