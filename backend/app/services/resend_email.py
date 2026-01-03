from __future__ import annotations

import logging
from typing import Any

import resend

from app.core.config import settings

logger = logging.getLogger(__name__)


class ResendConfigurationError(RuntimeError):
    """Raised when Resend is not configured properly."""


class ResendSendError(RuntimeError):
    """Raised when Resend fails to deliver an email."""


def _require_config() -> None:
    if not settings.RESEND_API_KEY:
        raise ResendConfigurationError("RESEND_API_KEY is not configured")
    if not settings.RESEND_FROM_EMAIL:
        raise ResendConfigurationError("RESEND_FROM_EMAIL is not configured")


def send_email_verification_code(*, to_email: str, code: str, expires_minutes: int) -> None:
    """
    Send the 6-digit verification code via Resend.

    Args:
        to_email: Recipient email address.
        code: 6-digit code (string).
        expires_minutes: TTL in minutes.
    """

    _require_config()

    resend.api_key = settings.RESEND_API_KEY

    subject = "Verify your Job Tracker email"
    expires_text = f"{expires_minutes} minute{'s' if expires_minutes != 1 else ''}"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background: #0f172a; padding: 24px; color: #f8fafc;">
        <div style="max-width: 520px; margin: 0 auto; background: #111827; border-radius: 12px; padding: 32px;">
          <h2 style="margin-top: 0; font-size: 1.5rem; color: #f8fafc;">Verify your email</h2>
          <p style="line-height: 1.6; color: #e2e8f0;">
            Enter the code below in Job Tracker to verify your email. This code expires in {expires_text}.
          </p>
          <div style="margin: 24px 0; background: #38bdf8; color: #0f172a; font-size: 32px; letter-spacing: 8px; text-align: center; padding: 18px; border-radius: 10px;">
            {code}
          </div>
          <p style="line-height: 1.6; color: #94a3b8;">
            Didn’t request this? Ignore the message or let us know at {settings.RESEND_FROM_EMAIL or 'support'}.
          </p>
        </div>
      </body>
    </html>
    """.strip()

    text_body = f"""
Verify your Job Tracker email

Enter this code in the app (expires in {expires_text}):

{code}

If you didn’t request this, ignore the message.
""".strip()

    try:
        payload: dict[str, Any] = {
            "from": settings.RESEND_FROM_EMAIL,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
        resend.Emails.send(payload)
        logger.info("Sent verification code via Resend to %s", to_email)
    except Exception as exc:  # pragma: no cover - resent lib raises runtime-specific errors
        logger.exception("Resend email send failure: %s", exc)
        raise ResendSendError("Unable to send verification email right now.") from exc


