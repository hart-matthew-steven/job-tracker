# app/models/refresh_token.py
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Store ONLY a hash of the refresh token (never store raw refresh token)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)

    # Absolute expiration for this refresh token
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # If set, token is no longer valid
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="refresh_tokens")
