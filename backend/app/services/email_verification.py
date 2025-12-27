from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.orm import Session

from app.core.security import create_email_verification_token
from app.models.email_verification_token import EmailVerificationToken
from app.models.user import User


def _hash_token_id(token_id: str) -> str:
    return sha256(token_id.encode("utf-8")).hexdigest()


def issue_email_verification_token(db: Session, user: User) -> str:
    """
    Generates a new verification token JWT for the given user, stores a hashed token id
    so it can be verified/invalidated later, and returns the raw token string.
    """
    token, token_id, expires_at = create_email_verification_token(email=user.email)

    # Remove any previously active tokens so only the latest link works.
    (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.user_id == user.id, EmailVerificationToken.used_at.is_(None))
        .delete(synchronize_session=False)
    )

    db.add(
        EmailVerificationToken(
            user_id=user.id,
            token_hash=_hash_token_id(token_id),
            expires_at=expires_at,
        )
    )
    db.flush()
    return token


def consume_email_verification_token(db: Session, user: User, token_id: str) -> None:
    """
    Marks the verification token as used. Raises ValueError if the token is invalid.
    """
    hashed = _hash_token_id(token_id)
    record = (
        db.query(EmailVerificationToken)
        .filter(EmailVerificationToken.token_hash == hashed)
        .first()
    )

    if not record:
        raise ValueError("Invalid or expired token")
    if record.user_id != user.id:
        raise ValueError("Invalid or expired token")
    if record.used_at is not None:
        raise ValueError("Invalid or expired token")

    now = datetime.now(timezone.utc)
    expires_at = record.expires_at
    if expires_at is None:
        raise ValueError("Invalid or expired token")
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise ValueError("Invalid or expired token")

    record.used_at = now
    db.add(record)

