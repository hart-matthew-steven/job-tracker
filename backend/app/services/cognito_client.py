"""
Wrapper around boto3 Cognito Identity Provider APIs.

Provides a stable, exception-friendly interface for the backend routes to call
without leaking boto3-specific errors up the stack.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List
from urllib.parse import quote

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class CognitoClientError(Exception):
    """Raised when Cognito returns an error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _require_cognito_client_config(require_user_pool: bool = False) -> None:
    if not settings.COGNITO_REGION:
        raise RuntimeError("COGNITO_REGION is not configured")
    if not settings.COGNITO_APP_CLIENT_ID:
        raise RuntimeError("COGNITO_APP_CLIENT_ID is not configured")
    if require_user_pool and not settings.COGNITO_USER_POOL_ID:
        raise RuntimeError("COGNITO_USER_POOL_ID is not configured")


@lru_cache(maxsize=1)
def _get_cognito_client(require_user_pool: bool = False):
    _require_cognito_client_config(require_user_pool=require_user_pool)
    return boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)


def _translate_error(exc: ClientError) -> CognitoClientError:
    error = exc.response.get("Error", {})
    code = error.get("Code", "CognitoClientError")
    message = error.get("Message", str(exc))
    return CognitoClientError(code=code, message=message)


def cognito_sign_up(email: str, password: str, name: str) -> dict:
    """Call Cognito SignUp API."""
    client = _get_cognito_client()
    try:
        resp = client.sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email,
            Password=password,
            UserAttributes=[
                {"Name": "email", "Value": email},
                {"Name": "name", "Value": name},
            ],
        )
        return resp
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_confirm_sign_up(email: str, code: str) -> None:
    """Confirm user signup with verification code."""
    client = _get_cognito_client()
    try:
        client.confirm_sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email,
            ConfirmationCode=code,
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_initiate_auth(email: str, password: str) -> dict:
    """Initiate USER_PASSWORD_AUTH flow."""
    client = _get_cognito_client()
    try:
        return client.initiate_auth(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={
                "USERNAME": email,
                "PASSWORD": password,
            },
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_refresh_auth(refresh_token: str) -> dict:
    """Initiate REFRESH_TOKEN_AUTH flow."""
    client = _get_cognito_client()
    try:
        return client.initiate_auth(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            AuthFlow="REFRESH_TOKEN_AUTH",
            AuthParameters={
                "REFRESH_TOKEN": refresh_token,
            },
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_respond_to_challenge(session: str, challenge_name: str, responses: dict[str, str]) -> dict:
    """Respond to an auth challenge (MFA, etc.)."""
    client = _get_cognito_client()
    try:
        return client.respond_to_auth_challenge(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            ChallengeName=challenge_name,
            ChallengeResponses=responses,
            Session=session,
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_associate_software_token(session: str | None = None, access_token: str | None = None) -> dict:
    """
    Associate a software token (TOTP).

    Provide either session (preferred during MFA_SETUP) or access_token.
    """
    if not session and not access_token:
        raise ValueError("session or access_token is required")

    client = _get_cognito_client()
    try:
        kwargs: Dict[str, Any] = {}
        if session:
            kwargs["Session"] = session
        if access_token:
            kwargs["AccessToken"] = access_token
        return client.associate_software_token(**kwargs)
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_verify_software_token(
    code: str,
    *,
    session: str | None = None,
    access_token: str | None = None,
    friendly_name: str | None = None,
) -> dict:
    """Verify the software token (TOTP) during setup."""
    if not session and not access_token:
        raise ValueError("session or access_token is required")

    client = _get_cognito_client()
    try:
        kwargs: Dict[str, Any] = {
            "UserCode": code,
        }
        if friendly_name:
            kwargs["FriendlyDeviceName"] = friendly_name
        if session:
            kwargs["Session"] = session
        if access_token:
            kwargs["AccessToken"] = access_token
        return client.verify_software_token(**kwargs)
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_set_user_mfa_preference(access_token: str, enable_totp: bool) -> None:
    """Enable or disable TOTP MFA for a user."""
    client = _get_cognito_client()
    try:
        client.set_user_mfa_preference(
            SoftwareTokenMfaSettings={
                "Enabled": enable_totp,
                "PreferredMfa": enable_totp,
            },
            AccessToken=access_token,
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


def cognito_get_user(access_token: str) -> dict[str, str]:
    """Fetch user attributes using an access token."""
    client = _get_cognito_client()
    try:
        resp = client.get_user(AccessToken=access_token)
    except ClientError as exc:
        raise _translate_error(exc) from exc

    attributes = {attr["Name"]: attr["Value"] for attr in resp.get("UserAttributes", [])}
    if "Username" not in attributes and resp.get("Username"):
        attributes["Username"] = resp["Username"]
    return attributes


def build_otpauth_uri(secret_code: str, email: str | None = None) -> str:
    """Return an otpauth:// URI for QR code generation."""
    label = email or "jobapptracker"
    issuer = "Job Tracker"
    safe_label = quote(label)
    safe_issuer = quote(issuer)
    return f"otpauth://totp/{safe_label}?secret={secret_code}&issuer={safe_issuer}"


def cognito_admin_mark_email_verified(*, cognito_sub: str, email: str | None = None) -> None:
    """Mark a Cognito user as email-verified via the AdminUpdateUserAttributes API."""
    if not cognito_sub:
        raise ValueError("cognito_sub is required to update Cognito attributes")

    client = _get_cognito_client(require_user_pool=True)
    attributes: List[dict[str, str]] = [
        {"Name": "email_verified", "Value": "true"},
    ]
    if email:
        attributes.append({"Name": "email", "Value": email})

    try:
        client.admin_update_user_attributes(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=cognito_sub,
            UserAttributes=attributes,
        )
    except ClientError as exc:
        raise _translate_error(exc) from exc


