from __future__ import annotations

import httpx

from app.core.config import settings

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
TURNSTILE_TIMEOUT = 5.0


class TurnstileError(Exception):
    """Base exception for Turnstile verification failures."""


class TurnstileConfigurationError(TurnstileError):
    """Raised when Turnstile is not configured correctly."""


class TurnstileVerificationError(TurnstileError):
    """Raised when Turnstile rejects a token or the call fails."""


def verify_turnstile_token(token: str, *, remote_ip: str | None = None) -> None:
    """
    Validate a Turnstile token with Cloudflare.

    Raises:
        TurnstileConfigurationError: if the secret key is missing.
        TurnstileVerificationError: if the verification fails.
    """

    secret = settings.TURNSTILE_SECRET_KEY
    if not secret:
        raise TurnstileConfigurationError("Turnstile secret key is not configured.")

    candidate = (token or "").strip()
    if not candidate:
        raise TurnstileVerificationError("Missing CAPTCHA token.")

    data: dict[str, str] = {
        "secret": secret,
        "response": candidate,
    }
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        response = httpx.post(TURNSTILE_VERIFY_URL, data=data, timeout=TURNSTILE_TIMEOUT)
    except httpx.HTTPError as exc:
        raise TurnstileVerificationError("Unable to verify CAPTCHA token.") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise TurnstileVerificationError("Invalid CAPTCHA response.") from exc

    if not bool(payload.get("success")):
        raise TurnstileVerificationError("CAPTCHA verification failed.")


