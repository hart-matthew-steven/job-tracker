from __future__ import annotations

import logging

import boto3
import httpx
import resend
import smtplib
from html import escape as html_escape
from email.mime.text import MIMEText
from email.utils import formatdate

from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError, EndpointConnectionError

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailNotConfiguredError(RuntimeError):
    pass


class EmailDeliveryError(RuntimeError):
    """
    Raised when a provider is configured but delivery fails.
    Message should be safe to surface to clients in dev.
    """


def _require_smtp_config() -> None:
    if not settings.SMTP_HOST:
        raise EmailNotConfiguredError("SMTP_HOST is not set")
    if not settings.SMTP_FROM_EMAIL:
        raise EmailNotConfiguredError("SMTP_FROM_EMAIL is not set")

    # Username/password may be optional for some SMTP servers, so don't hard-require.


def _normalize_provider(raw: str | None) -> str:
    """
    Supported providers:
    - resend (default when unset)
    - ses
    - gmail
    Legacy alias:
    - smtp -> gmail
    """
    provider = (raw or "").strip().lower()
    if not provider:
        return "resend"
    if provider == "smtp":
        return "gmail"
    if provider in {"resend", "ses", "gmail"}:
        return provider
    raise EmailNotConfiguredError(
        f"Unsupported EMAIL_PROVIDER={provider!r}. Supported: resend (default), ses, gmail. Legacy alias: smtp -> gmail."
    )


def _require_from_email() -> str:
    """
    FROM_EMAIL is used only for: ses, resend.
    Do not use FROM_EMAIL for gmail/smtp (preserve SMTP-authenticated From behavior).
    """
    if not settings.FROM_EMAIL:
        raise EmailNotConfiguredError("FROM_EMAIL is not set")
    return settings.FROM_EMAIL


def _require_ses_config() -> tuple[str, str]:
    region = (settings.AWS_REGION or "").strip()
    if not region:
        raise EmailNotConfiguredError("AWS_REGION is not set (required for SES)")
    return region, _require_from_email()


def _require_resend_config() -> tuple[str, str]:
    api_key = (settings.RESEND_API_KEY or "").strip()
    if not api_key:
        raise EmailNotConfiguredError("RESEND_API_KEY is not set")
    return api_key, _require_from_email()


def _send_email_ses(to_email: str, subject: str, body: str) -> str | None:
    region, from_email = _require_ses_config()
    client = boto3.client("ses", region_name=region)

    try:
        res = client.send_email(
            Source=from_email,
            Destination={"ToAddresses": [to_email]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
        msg_id = res.get("MessageId")
        logger.info("SES email sent: to=%s msg_id=%s", to_email, msg_id)
        return msg_id
    except NoCredentialsError as e:
        logger.exception("SES email failed (no AWS credentials)")
        raise EmailDeliveryError("SES email failed: AWS credentials not available") from e
    except EndpointConnectionError as e:
        logger.exception("SES email failed (endpoint connection)")
        raise EmailDeliveryError("SES email failed: could not connect to SES endpoint") from e
    except ClientError as e:
        logger.exception("SES email failed (client error)")
        # Provide a short, user-friendly message while keeping details out of the client.
        code = (e.response or {}).get("Error", {}).get("Code", "ClientError")
        if code in {"MessageRejected", "MailFromDomainNotVerifiedException"}:
            raise EmailDeliveryError(
                "SES rejected the email. Verify FROM_EMAIL (or domain) and check if SES is in sandbox."
            ) from e
        raise EmailDeliveryError(f"SES email failed: {code}") from e
    except BotoCoreError as e:
        logger.exception("SES email failed (botocore)")
        raise EmailDeliveryError("SES email failed") from e


def _send_email_resend(to_email: str, subject: str, body: str) -> str | None:
    api_key, from_email = _require_resend_config()

    # Reuse existing plain-text body; provide a minimal HTML variant.
    html = f"<pre>{html_escape(body)}</pre>"

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": body,
        "html": html,
    }

    try:
        # Use Resend's official Python SDK.
        resend.api_key = api_key
        res = resend.Emails.send(payload)  # type: ignore[attr-defined]
    except Exception as e:  # noqa: BLE001
        raise EmailDeliveryError(f"Resend send failed: {e}") from e

    # Best-effort message id extraction
    msg_id: str | None = None
    try:
        if isinstance(res, dict):
            if res.get("error"):
                raise EmailDeliveryError(f"Resend API error: {res.get('error')}")
            v = res.get("id")
            if isinstance(v, str) and v.strip():
                msg_id = v.strip()
    except Exception:
        pass

    logger.info("Resend email sent: to=%s msg_id=%s", to_email, msg_id)
    return msg_id


def _send_email_smtp(to_email: str, subject: str, body: str) -> None:
    """
    Send a plaintext email via SMTP using stdlib only.
    """
    _require_smtp_config()

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)

    if settings.SMTP_USE_SSL:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)

    try:
        server.ehlo()
        if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
            server.starttls()
            server.ehlo()

        if settings.SMTP_USERNAME:
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

        server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
    finally:
        try:
            server.quit()
        except Exception:
            pass


def send_email(to_email: str, subject: str, body: str) -> str | None:
    """
    Sends email using configured provider.
    - EMAIL_PROVIDER=resend (default): Resend API
    - EMAIL_PROVIDER=ses: AWS SES via boto3
    - EMAIL_PROVIDER=gmail: SMTP via stdlib (preserves SMTP_FROM_EMAIL From behavior)
    - EMAIL_PROVIDER=smtp: legacy alias for gmail
    """
    provider = _normalize_provider(settings.EMAIL_PROVIDER)
    if provider == "gmail":
        _send_email_smtp(to_email=to_email, subject=subject, body=body)
        return None
    if provider == "ses":
        return _send_email_ses(to_email=to_email, subject=subject, body=body)
    return _send_email_resend(to_email=to_email, subject=subject, body=body)

