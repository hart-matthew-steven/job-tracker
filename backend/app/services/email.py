from __future__ import annotations

import logging

import boto3
import smtplib
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

def _require_ses_config() -> tuple[str, str]:
    region = (settings.SES_REGION or settings.AWS_REGION or "").strip()
    if not region:
        raise EmailNotConfiguredError("SES_REGION (or AWS_REGION) is not set")
    if not settings.SES_FROM_EMAIL:
        raise EmailNotConfiguredError("SES_FROM_EMAIL is not set")
    return region, settings.SES_FROM_EMAIL


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
                "SES rejected the email. Verify SES_FROM_EMAIL (or domain) and check if SES is in sandbox."
            ) from e
        raise EmailDeliveryError(f"SES email failed: {code}") from e
    except BotoCoreError as e:
        logger.exception("SES email failed (botocore)")
        raise EmailDeliveryError("SES email failed") from e


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
    - EMAIL_PROVIDER=ses (default): AWS SES via boto3
    - EMAIL_PROVIDER=smtp: SMTP via stdlib
    """
    provider = (settings.EMAIL_PROVIDER or "ses").strip().lower()
    if provider == "smtp":
        _send_email_smtp(to_email=to_email, subject=subject, body=body)
        return None
    return _send_email_ses(to_email=to_email, subject=subject, body=body)

