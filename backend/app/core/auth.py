# app/core/auth.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# -----------------------
# Password hashing
# -----------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


# -----------------------
# JWT helpers (pure)
# -----------------------
def create_access_token(subject: str) -> str:
    """
    subject: typically user's email
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Returns decoded JWT payload (dict) or raises JWTError.
    Keep this "pure" — no FastAPI/HTTPException here.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def get_token_subject(token: str) -> str:
    """
    Returns normalized subject (email) from token or raises ValueError/JWTError.
    """
    payload = decode_access_token(token)
    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token missing 'sub'")
    return str(sub).strip().lower()