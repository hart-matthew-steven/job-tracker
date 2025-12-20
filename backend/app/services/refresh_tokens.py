from __future__ import annotations

import hmac
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.refresh_token import RefreshToken


# -----------------------------
# Refresh token settings
# -----------------------------
def refresh_token_expiry() -> datetime:
    hours = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_HOURS", 24))
    return datetime.now(timezone.utc) + timedelta(hours=hours)


def refresh_cookie_max_age_seconds() -> int:
    hours = int(getattr(settings, "REFRESH_TOKEN_EXPIRE_HOURS", 24))
    return hours * 3600


def hash_refresh_token(raw_token: str) -> str:
    """
    Store only a hash in DB.
    Use HMAC keyed by JWT_SECRET so DB leaks can't be brute-forced easily.
    """
    secret = (settings.JWT_SECRET or "").encode("utf-8")
    if not secret:
        raise RuntimeError("JWT_SECRET must be set to hash refresh tokens.")
    return hmac.new(secret, raw_token.encode("utf-8"), hashlib.sha256).hexdigest()


def issue_refresh_token(db: Session, user_id: int) -> str:
    """
    Creates a new refresh token for user, stores hash in DB, returns raw token.
    """
    raw = secrets.token_urlsafe(48)  # long random string
    token_hash = hash_refresh_token(raw)

    rt = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=refresh_token_expiry(),
        revoked_at=None,
    )
    db.add(rt)
    db.commit()
    return raw


def revoke_refresh_token(db: Session, token_hash: str) -> None:
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not rt:
        return
    if rt.revoked_at is None:
        rt.revoked_at = datetime.now(timezone.utc)
        db.commit()


def get_valid_refresh_token(db: Session, raw_refresh_token: str) -> RefreshToken | None:
    token_hash = hash_refresh_token(raw_refresh_token)
    rt = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    if not rt:
        return None

    now = datetime.now(timezone.utc)
    if rt.revoked_at is not None:
        return None
    # SQLite may round-trip tz-aware datetimes as naive. Compare consistently.
    expires_at = rt.expires_at
    if expires_at is None:
        return None
    if getattr(expires_at, "tzinfo", None) is None and now.tzinfo is not None:
        now_cmp = now.replace(tzinfo=None)
    else:
        now_cmp = now
    if expires_at <= now_cmp:
        return None

    return rt


# -----------------------------
# Cookie helpers
# -----------------------------
def cookie_name() -> str:
    return str(getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")).strip() or "refresh_token"


def cookie_path() -> str:
    # Keep refresh cookie scoped to auth endpoints by default
    return str(getattr(settings, "REFRESH_COOKIE_PATH", "/auth")).strip() or "/auth"


def cookie_secure() -> bool:
    # Prod => HTTPS => Secure cookies. Dev http://localhost => must be False.
    return settings.is_prod


def cookie_samesite() -> str:
    """
    "lax" for same-site dev
    "none" ONLY if you truly need cross-site cookies (requires HTTPS + Secure=True)
    """
    v = str(getattr(settings, "REFRESH_COOKIE_SAMESITE", "lax")).lower().strip()
    if v not in {"lax", "strict", "none"}:
        return "lax"
    return v


def set_refresh_cookie(resp: Response, raw_refresh_token: str) -> None:
    resp.set_cookie(
        key=cookie_name(),
        value=raw_refresh_token,
        httponly=True,
        secure=cookie_secure(),
        samesite=cookie_samesite(),
        max_age=refresh_cookie_max_age_seconds(),
        path=cookie_path(),
    )


def clear_refresh_cookie(resp: Response) -> None:
    resp.delete_cookie(
        key=cookie_name(),
        path=cookie_path(),
    )


def read_refresh_cookie(req: Request) -> str | None:
    val = req.cookies.get(cookie_name())
    if not val:
        return None
    val = val.strip()
    return val or None


