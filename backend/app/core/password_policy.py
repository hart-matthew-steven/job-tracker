from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, List

from fastapi import HTTPException, status

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.user import User

COMMON_WEAK_PASSWORDS = {
    "password",
    "password123",
    "123456",
    "123456789",
    "12345678",
    "qwerty",
    "abc123",
    "letmein",
    "111111",
    "iloveyou",
    "admin",
    "welcome",
    "monkey",
    "dragon",
    "football",
    "baseball",
    "123123",
    "qwerty123",
    "zaq12wsx",
    "trustno1",
    "passw0rd",
    "sunshine",
    "princess",
    "login",
    "whatever",
}

_UPPERCASE_RE = re.compile(r"[A-Z]")
_LOWERCASE_RE = re.compile(r"[a-z]")
_NUMBER_RE = re.compile(r"[0-9]")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


def _normalize(value: str | None) -> str:
    return (value or "").strip().lower()


def evaluate_password(
    password: str,
    *,
    email: str | None = None,
    username: str | None = None,
) -> List[str]:
    """
    Returns a list of violation codes if the password does not meet policy.
    """
    pw = password or ""
    violations: list[str] = []
    min_length = max(int(getattr(settings, "PASSWORD_MIN_LENGTH", 14) or 0), 1)

    if len(pw) < min_length:
        violations.append("min_length")
    if not _UPPERCASE_RE.search(pw):
        violations.append("uppercase")
    if not _LOWERCASE_RE.search(pw):
        violations.append("lowercase")
    if not _NUMBER_RE.search(pw):
        violations.append("number")
    if not _SPECIAL_RE.search(pw):
        violations.append("special_char")

    normalized_pw = pw.lower()

    email_norm = _normalize(email)
    if email_norm and email_norm in normalized_pw:
        violations.append("contains_email")
    else:
        local_part = email_norm.split("@")[0] if email_norm else ""
        if local_part and local_part in normalized_pw:
            violations.append("contains_email")

    username_norm = _normalize(username)
    if username_norm and username_norm in normalized_pw:
        violations.append("contains_name")

    if normalized_pw in COMMON_WEAK_PASSWORDS:
        violations.append("denylist_common")

    # Remove duplicates while preserving original order.
    seen = set()
    result: list[str] = []
    for v in violations:
        if v in seen:
            continue
        seen.add(v)
        result.append(v)
    return result


def ensure_strong_password(password: str, *, email: str | None = None, username: str | None = None) -> None:
    violations = evaluate_password(password, email=email, username=username)
    if violations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Password does not meet requirements.",
                "details": {"code": "WEAK_PASSWORD", "violations": violations},
            },
        )

