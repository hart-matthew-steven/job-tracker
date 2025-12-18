# app/core/security.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
import secrets
from hashlib import sha256

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# -------------------------
# Password hashing
# -------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# -------------------------
# JWT helpers
# -------------------------
def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _require_jwt_secret() -> None:
    # Auth is always on -> JWT_SECRET must always exist
    if not settings.JWT_SECRET or not settings.JWT_SECRET.strip():
        raise RuntimeError("JWT_SECRET must be set (auth is required).")


def create_access_token(subject: str) -> str:
    """
    Access token used for API auth: Authorization: Bearer <token>
    subject = user's email in our flow
    """
    _require_jwt_secret()

    now = _now_utc()
    exp = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": subject,
        "purpose": "access",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_email_verification_token(email: str) -> str:
    """
    Token used for /auth/verify?token=...
    """
    _require_jwt_secret()

    now = _now_utc()
    exp = now + timedelta(hours=settings.EMAIL_VERIFY_TOKEN_EXPIRE_HOURS)

    payload = {
        "sub": email,
        "purpose": "email_verification",
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    _require_jwt_secret()
    # Let callers decide how to handle JWTError
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def verify_token_purpose(token: str, expected_purpose: str) -> dict[str, Any]:
    try:
        payload = decode_token(token)
    except JWTError:
        raise ValueError("Invalid or expired token")

    if payload.get("purpose") != expected_purpose:
        raise ValueError("Invalid token purpose")

    return payload


# -------------------------
# Refresh token helpers
# -------------------------
def generate_refresh_token() -> str:
    """
    Generate a cryptographically secure refresh token.
    This raw token is ONLY returned to the client once.
    Backend stores ONLY a hash.
    """
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """
    Hash refresh token for DB storage (never store the raw token).
    """
    return sha256(token.encode("utf-8")).hexdigest()