from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.email_verification_code import EmailVerificationCode
from app.models.user import User
from app.services.resend_email import (
    ResendConfigurationError,
    ResendSendError,
    send_email_verification_code,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_code(code: str, salt: str) -> str:
    payload = f"{salt}:{code}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _active_codes_query(db: Session, user_id: int):
    return (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user_id,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
    )


def _validate_feature_enabled() -> None:
    if not settings.EMAIL_VERIFICATION_ENABLED:
        raise HTTPException(status_code=400, detail="Email verification is disabled.")


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def send_code(db: Session, *, user: User) -> EmailVerificationCode:
    _validate_feature_enabled()
    now = _now()
    ttl_seconds = max(60, settings.EMAIL_VERIFICATION_CODE_TTL_SECONDS)
    cooldown_seconds = max(10, settings.EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS)
    expires_at = now + timedelta(seconds=ttl_seconds)
    resend_available_at = now + timedelta(seconds=cooldown_seconds)

    active_code = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .first()
    )

    if active_code and _as_aware(active_code.resend_available_at) > now:
        raise HTTPException(
            status_code=429,
            detail="Please wait before requesting another verification code.",
        )

    # Invalidate older active codes
    db.query(EmailVerificationCode).filter(
        EmailVerificationCode.user_id == user.id,
        EmailVerificationCode.consumed_at.is_(None),
    ).update({EmailVerificationCode.consumed_at: now}, synchronize_session=False)

    code = f"{secrets.randbelow(10**6):06d}"
    salt = secrets.token_hex(8)
    record = EmailVerificationCode(
        user_id=user.id,
        code_hash=_hash_code(code, salt),
        code_salt=salt,
        expires_at=expires_at,
        resend_available_at=resend_available_at,
        max_attempts=settings.EMAIL_VERIFICATION_MAX_ATTEMPTS or 10,
    )

    db.add(record)
    db.flush()

    try:
        expires_minutes = max(1, ttl_seconds // 60)
        send_email_verification_code(to_email=user.email, code=code, expires_minutes=expires_minutes)
    except (ResendConfigurationError, ResendSendError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc))

    db.commit()
    return record


def validate_code(db: Session, *, user: User, code: str) -> EmailVerificationCode:
    _validate_feature_enabled()
    now = _now()
    normalized_code = code.strip()
    if len(normalized_code) != 6 or not normalized_code.isdigit():
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    record = (
        db.query(EmailVerificationCode)
        .filter(
            EmailVerificationCode.user_id == user.id,
            EmailVerificationCode.consumed_at.is_(None),
        )
        .order_by(EmailVerificationCode.created_at.desc())
        .with_for_update()
        .first()
    )

    if not record:
        raise HTTPException(status_code=400, detail="Verification code not found. Request a new one.")

    if _as_aware(record.expires_at) <= now:
        record.consumed_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Verification code has expired. Request a new one.")

    if record.attempts >= record.max_attempts:
        record.consumed_at = now
        db.commit()
        raise HTTPException(status_code=400, detail="Too many invalid attempts. Request a new code.")

    expected_hash = _hash_code(normalized_code, record.code_salt)
    if record.code_hash != expected_hash:
        record.attempts += 1
        db.commit()
        raise HTTPException(status_code=400, detail="Invalid verification code.")

    record.consumed_at = now
    return record


