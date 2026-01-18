from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.password_policy import ensure_strong_password
from app.schemas.auth_cognito import (
    CognitoAuthResponse,
    CognitoChallengeIn,
    CognitoConfirmIn,
    EmailVerificationConfirmIn,
    EmailVerificationSendIn,
    CognitoLoginIn,
    CognitoMessage,
    CognitoMfaSetupIn,
    CognitoMfaVerifyIn,
    CognitoRefreshIn,
    CognitoSecretOut,
    CognitoSignupIn,
    CognitoTokens,
    EmailVerificationSendOut,
)
from app.services.cognito_client import (
    CognitoClientError,
    build_otpauth_uri,
    cognito_associate_software_token,
    cognito_admin_mark_email_verified,
    cognito_confirm_sign_up,
    cognito_get_user,
    cognito_initiate_auth,
    cognito_refresh_auth,
    cognito_respond_to_challenge,
    cognito_sign_up,
    cognito_verify_software_token,
)
from app.dependencies.rate_limit import require_rate_limit
from app.services.turnstile import (
    TurnstileConfigurationError,
    TurnstileVerificationError,
    verify_turnstile_token,
)
from app.services.email_verification import send_code as send_verification_code, validate_code as validate_verification_code
from app.services.users import ensure_cognito_user, get_user_by_email
from app.models.user import User


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/cognito", tags=["auth", "cognito"])


def _auth_rate_limit(route_key: str, limit: int, window_seconds: int = 60):
    return Depends(
        require_rate_limit(
            route_key=route_key,
            limit=limit,
            window_seconds=window_seconds,
        )
    )


signup_rate_limit = _auth_rate_limit("auth_signup", 5)
confirm_rate_limit = _auth_rate_limit("auth_confirm", 8)
login_rate_limit = _auth_rate_limit("auth_login", 10)
challenge_rate_limit = _auth_rate_limit("auth_challenge", 10)
mfa_setup_rate_limit = _auth_rate_limit("auth_mfa_setup", 5)
mfa_verify_rate_limit = _auth_rate_limit("auth_mfa_verify", 10)
verification_send_rate_limit = _auth_rate_limit("auth_verification_send", 6)
verification_confirm_rate_limit = _auth_rate_limit("auth_verification_confirm", 10)
refresh_rate_limit = _auth_rate_limit("auth_refresh", 12)

CHALLENGE_STEP_MAP = {
    "MFA_SETUP": "MFA_SETUP",
    "SOFTWARE_TOKEN_MFA": "SOFTWARE_TOKEN_MFA",
    "NEW_PASSWORD_REQUIRED": "NEW_PASSWORD_REQUIRED",
    "CUSTOM_CHALLENGE": "CUSTOM_CHALLENGE",
}

CHALLENGE_DEFAULT_MESSAGE = "Additional authentication is required to finish signing in."
CHALLENGE_MESSAGE_MAP = {
    "MFA_SETUP": "Set up an authenticator app using the provided QR code.",
    "SOFTWARE_TOKEN_MFA": "Enter the 6-digit code from your authenticator app.",
    "NEW_PASSWORD_REQUIRED": "You must set a new password to continue.",
    "CUSTOM_CHALLENGE": "Complete the custom challenge to continue.",
    "UNKNOWN": CHALLENGE_DEFAULT_MESSAGE,
}

GENERIC_VERIFICATION_RESPONSE = "If the account exists, a verification code has been sent."


def _translate_cognito_error(exc: CognitoClientError) -> HTTPException:
    status = 400
    if exc.code in {"NotAuthorizedException", "UserNotFoundException"}:
        status = 401
    elif exc.code in {"TooManyRequestsException"}:
        status = 429
    elif exc.code in {"InternalErrorException"}:
        status = 503
    return HTTPException(status_code=status, detail=exc.args[0])


def _ensure_user_from_access_token(
    db: Session,
    *,
    access_token: str,
    fallback_email: str,
) -> None:
    try:
        attributes = cognito_get_user(access_token)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    cognito_sub = attributes.get("sub")
    email = attributes.get("email") or fallback_email
    name = attributes.get("name")

    if not cognito_sub or not email:
        raise HTTPException(status_code=500, detail="Cognito user profile missing required attributes")

    try:
        ensure_cognito_user(
            db,
            cognito_sub=cognito_sub,
            email=email,
            name=name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
def _map_next_step(challenge_name: str | None) -> str:
    if not challenge_name:
        return "UNKNOWN"
    return CHALLENGE_STEP_MAP.get(challenge_name, "UNKNOWN")


def _challenge_response(
    *,
    challenge_name: str | None,
    session: str | None,
    message: str | None = None,
) -> CognitoAuthResponse:
    if not session:
        raise HTTPException(status_code=500, detail="Missing Cognito session for challenge response.")
    next_step = _map_next_step(challenge_name)
    default_message = CHALLENGE_MESSAGE_MAP.get(next_step, CHALLENGE_DEFAULT_MESSAGE)
    return CognitoAuthResponse(
        status="CHALLENGE",
        next_step=next_step,
        challenge_name=challenge_name,
        session=session,
        message=message or default_message,
    )


def _normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _require_valid_email(value: str) -> str:
    normalized = _normalize_email(value)
    if not normalized or "@" not in normalized:
        raise HTTPException(status_code=400, detail="Valid email address required.")
    return normalized


def _build_token_payload(authentication: dict, *, fallback_refresh: str | None = None) -> CognitoTokens:
    access_token = authentication.get("AccessToken")
    if not access_token:
        raise HTTPException(status_code=500, detail="Missing AccessToken in Cognito response")

    refresh_token = authentication.get("RefreshToken") or fallback_refresh

    return CognitoTokens(
        access_token=access_token,
        id_token=authentication.get("IdToken"),
        refresh_token=refresh_token,
        expires_in=int(authentication.get("ExpiresIn") or 0),
        token_type=authentication.get("TokenType") or "Bearer",
    )


def _handle_auth_result(
    auth_result: dict,
    *,
    db: Session,
    fallback_email: str,
    fallback_refresh_token: str | None = None,
) -> CognitoAuthResponse:
    authentication = auth_result.get("AuthenticationResult")
    if not authentication:
        return _challenge_response(
            challenge_name=auth_result.get("ChallengeName"),
            session=auth_result.get("Session"),
        )

    tokens = _build_token_payload(authentication, fallback_refresh=fallback_refresh_token)
    _ensure_user_from_access_token(
        db,
        access_token=tokens.access_token,
        fallback_email=fallback_email,
    )

    return CognitoAuthResponse(
        status="OK",
        tokens=tokens,
        message=None,
    )


@router.post("/signup", response_model=CognitoMessage, dependencies=[signup_rate_limit])
def cognito_signup(
    request: Request,
    payload: CognitoSignupIn,
    db: Session = Depends(get_db),
):
    ensure_strong_password(payload.password, email=payload.email, username=payload.name)

    if not settings.TURNSTILE_SITE_KEY or not settings.TURNSTILE_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Signup is temporarily unavailable. Please try again later.",
        )

    client_ip = request.client.host if request.client else None
    try:
        verify_turnstile_token(payload.turnstile_token, remote_ip=client_ip)
    except TurnstileConfigurationError:
        raise HTTPException(
            status_code=503,
            detail="Signup is temporarily unavailable. Please try again later.",
        )
    except TurnstileVerificationError:
        raise HTTPException(
            status_code=400,
            detail="CAPTCHA verification failed. Please try again.",
        )

    try:
        resp = cognito_sign_up(payload.email, payload.password, payload.name.strip())
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    provisioned_user: User | None = None
    user_sub = resp.get("UserSub")
    if user_sub:
        try:
            provisioned_user = ensure_cognito_user(
                db,
                cognito_sub=user_sub,
                email=payload.email,
                name=payload.name,
            )
        except ValueError as exc:
            logger.warning("Unable to ensure Cognito user after signup: %s", exc)

    if settings.EMAIL_VERIFICATION_ENABLED and provisioned_user:
        try:
            send_verification_code(db, user=provisioned_user)
        except HTTPException as exc:
            detail = getattr(exc, "detail", str(exc))
            logger.warning("Auto-send verification email failed: %s", detail)

    status = "OK" if resp.get("UserConfirmed") else "CONFIRMATION_REQUIRED"
    if settings.EMAIL_VERIFICATION_ENABLED:
        message = "Account created. Enter the verification code we emailed you."
    else:
        message = "Confirmation code sent to email." if status == "CONFIRMATION_REQUIRED" else "Signup successful."
    return CognitoMessage(status=status, message=message)


@router.post("/confirm", response_model=CognitoMessage, dependencies=[confirm_rate_limit])
def cognito_confirm(request: Request, payload: CognitoConfirmIn):
    try:
        cognito_confirm_sign_up(payload.email, payload.code)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)
    return CognitoMessage(status="OK", message="Account confirmed. You can now log in.")


@router.post("/login", response_model=CognitoAuthResponse, dependencies=[login_rate_limit])
def cognito_login(
    request: Request,
    payload: CognitoLoginIn,
    db: Session = Depends(get_db),
):
    try:
        auth_result = cognito_initiate_auth(payload.email, payload.password)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    if auth_result.get("ChallengeName"):
        return _challenge_response(
            challenge_name=auth_result.get("ChallengeName"),
            session=auth_result.get("Session"),
        )

    return _handle_auth_result(auth_result, db=db, fallback_email=payload.email)


@router.post("/challenge", response_model=CognitoAuthResponse, dependencies=[challenge_rate_limit])
def cognito_challenge(
    request: Request,
    payload: CognitoChallengeIn,
    db: Session = Depends(get_db),
):
    if not payload.responses.get("USERNAME"):
        payload.responses["USERNAME"] = payload.email

    try:
        challenge_result = cognito_respond_to_challenge(
            payload.session,
            payload.challenge_name,
            payload.responses,
        )
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    if challenge_result.get("ChallengeName"):
        return _challenge_response(
            challenge_name=challenge_result.get("ChallengeName"),
            session=challenge_result.get("Session"),
        )

    return _handle_auth_result(challenge_result, db=db, fallback_email=payload.email)


@router.post("/mfa/setup", response_model=CognitoSecretOut, dependencies=[mfa_setup_rate_limit])
def cognito_mfa_setup(request: Request, payload: CognitoMfaSetupIn):
    try:
        assoc = cognito_associate_software_token(session=payload.session)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    secret = assoc.get("SecretCode")
    if not secret:
        raise HTTPException(status_code=500, detail="Missing SecretCode from Cognito")

    otpauth_uri = build_otpauth_uri(secret, payload.label)
    return CognitoSecretOut(secret_code=secret, session=assoc.get("Session"), otpauth_uri=otpauth_uri)


@router.post("/mfa/verify", response_model=CognitoAuthResponse, dependencies=[mfa_verify_rate_limit])
def cognito_mfa_verify(
    request: Request,
    payload: CognitoMfaVerifyIn,
    db: Session = Depends(get_db),
):
    try:
        verify_resp = cognito_verify_software_token(
            payload.code,
            session=payload.session,
            friendly_name=payload.friendly_name,
        )
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    session = verify_resp.get("Session") or payload.session
    challenge_result = cognito_respond_to_challenge(
        session,
        "MFA_SETUP",
        {"USERNAME": payload.email, "ANSWER": "SUCCESS"},
    )

    if challenge_result.get("ChallengeName"):
        return _challenge_response(
            challenge_name=challenge_result.get("ChallengeName"),
            session=challenge_result.get("Session"),
        )

    return _handle_auth_result(
        challenge_result,
        db=db,
        fallback_email=payload.email,
    )


@router.post(
    "/verification/send",
    response_model=EmailVerificationSendOut,
    dependencies=[verification_send_rate_limit],
)
def send_verification_code_route(
    request: Request,
    payload: EmailVerificationSendIn,
    db: Session = Depends(get_db),
):
    if not settings.EMAIL_VERIFICATION_ENABLED:
        return CognitoMessage(status="OK", message="Email verification is disabled.")

    normalized_email = _require_valid_email(payload.email)
    user = get_user_by_email(db, normalized_email)
    if not user:
        return EmailVerificationSendOut(status="OK", message=GENERIC_VERIFICATION_RESPONSE)

    if user.is_email_verified:
        return EmailVerificationSendOut(status="OK", message="Email is already verified.")

    record = send_verification_code(db, user=user)
    resend_available_at = record.resend_available_at
    if resend_available_at.tzinfo is None:
        resend_available_at = resend_available_at.replace(tzinfo=timezone.utc)
    else:
        resend_available_at = resend_available_at.astimezone(timezone.utc)
    cooldown_seconds = max(
        0, int((resend_available_at - datetime.now(timezone.utc)).total_seconds())
    )
    return EmailVerificationSendOut(
        status="OK",
        message="Verification code sent.",
        resend_available_in_seconds=cooldown_seconds,
    )


@router.post(
    "/verification/confirm",
    response_model=CognitoMessage,
    dependencies=[verification_confirm_rate_limit],
)
def confirm_verification_code(
    request: Request,
    payload: EmailVerificationConfirmIn,
    db: Session = Depends(get_db),
):
    if not settings.EMAIL_VERIFICATION_ENABLED:
        return CognitoMessage(status="OK", message="Email verification is disabled.")

    normalized_email = _require_valid_email(payload.email)
    user = get_user_by_email(db, normalized_email)
    if not user:
        raise HTTPException(status_code=400, detail="Verification code not found. Request a new one.")

    if user.is_email_verified:
        return CognitoMessage(status="OK", message="Email is already verified.")

    record = validate_verification_code(db, user=user, code=payload.code)

    try:
        cognito_admin_mark_email_verified(cognito_sub=user.cognito_sub, email=user.email)
    except CognitoClientError as exc:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Unable to update Cognito user attributes. Please try again in a moment.",
        ) from exc

    now = datetime.now(timezone.utc)
    db_user = (
        db.query(User)
        .filter(User.id == user.id)
        .with_for_update()
        .one()
    )
    db_user.is_email_verified = True
    db_user.email_verified_at = now
    record.updated_at = now
    db.commit()

    return CognitoMessage(
        status="OK",
        message="Email verified. Sign in again to finish MFA setup before using the app.",
    )


@router.post("/refresh", response_model=CognitoAuthResponse, dependencies=[refresh_rate_limit])
def cognito_refresh(
    request: Request,
    payload: CognitoRefreshIn,
    db: Session = Depends(get_db),
):
    try:
        auth_result = cognito_refresh_auth(payload.refresh_token)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)

    return _handle_auth_result(
        auth_result,
        db=db,
        fallback_email="",
        fallback_refresh_token=payload.refresh_token,
    )


@router.post("/logout", response_model=CognitoMessage)
def cognito_logout(request: Request):
    """Placeholder logout endpoint for API parity."""
    return CognitoMessage(status="OK", message="Logged out")


