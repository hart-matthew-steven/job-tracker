from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.password_policy import ensure_strong_password
from app.schemas.auth_cognito import (
    CognitoAuthResponse,
    CognitoChallengeIn,
    CognitoConfirmIn,
    CognitoLoginIn,
    CognitoMessage,
    CognitoMfaSetupIn,
    CognitoMfaVerifyIn,
    CognitoRefreshIn,
    CognitoSecretOut,
    CognitoSignupIn,
    CognitoTokens,
)
from app.core.rate_limit import limiter
from app.services.cognito_client import (
    CognitoClientError,
    build_otpauth_uri,
    cognito_associate_software_token,
    cognito_confirm_sign_up,
    cognito_get_user,
    cognito_initiate_auth,
    cognito_refresh_auth,
    cognito_respond_to_challenge,
    cognito_sign_up,
    cognito_verify_software_token,
)
from app.services.turnstile import (
    TurnstileConfigurationError,
    TurnstileVerificationError,
    verify_turnstile_token,
)
from app.services.users import ensure_cognito_user


router = APIRouter(prefix="/auth/cognito", tags=["auth", "cognito"])

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


@router.post("/signup", response_model=CognitoMessage)
@limiter.limit("5/minute")
def cognito_signup(request: Request, payload: CognitoSignupIn):
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

    status = "OK" if resp.get("UserConfirmed") else "CONFIRMATION_REQUIRED"
    message = "Confirmation code sent to email." if status == "CONFIRMATION_REQUIRED" else "Signup successful."
    return CognitoMessage(status=status, message=message)


@router.post("/confirm", response_model=CognitoMessage)
@limiter.limit("8/minute")
def cognito_confirm(request: Request, payload: CognitoConfirmIn):
    try:
        cognito_confirm_sign_up(payload.email, payload.code)
    except CognitoClientError as exc:
        raise _translate_cognito_error(exc)
    return CognitoMessage(status="OK", message="Account confirmed. You can now log in.")


@router.post("/login", response_model=CognitoAuthResponse)
@limiter.limit("10/minute")
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


@router.post("/challenge", response_model=CognitoAuthResponse)
@limiter.limit("10/minute")
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


@router.post("/mfa/setup", response_model=CognitoSecretOut)
@limiter.limit("5/minute")
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


@router.post("/mfa/verify", response_model=CognitoAuthResponse)
@limiter.limit("10/minute")
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


@router.post("/refresh", response_model=CognitoAuthResponse)
@limiter.limit("12/minute")
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


