"""
Pydantic schemas for Cognito Option B (BFF) authentication flows.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, constr

class CognitoTokens(BaseModel):
    access_token: str
    id_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: int
    token_type: str = "Bearer"

class CognitoSignupIn(BaseModel):
    email: EmailStr
    password: constr(min_length=8)
    name: constr(min_length=1, max_length=100)
    turnstile_token: constr(min_length=1) = Field(..., description="Cloudflare Turnstile response token")


class CognitoConfirmIn(BaseModel):
    email: EmailStr
    code: constr(min_length=1, max_length=10)


class EmailVerificationSendIn(BaseModel):
    email: constr(min_length=3)


class EmailVerificationSendOut(BaseModel):
    status: str = "OK"
    message: str | None = None
    resend_available_in_seconds: int | None = None


class EmailVerificationConfirmIn(BaseModel):
    email: constr(min_length=3)
    code: constr(min_length=6, max_length=6)


class CognitoLoginIn(BaseModel):
    email: EmailStr
    password: constr(min_length=8)


class CognitoRefreshIn(BaseModel):
    refresh_token: constr(min_length=10)


class CognitoChallengeIn(BaseModel):
    email: EmailStr
    challenge_name: str = Field(..., description="ChallengeName from Cognito (e.g., SOFTWARE_TOKEN_MFA)")
    session: str
    responses: dict[str, str] = Field(
        default_factory=dict,
        description="ChallengeResponses map to forward to Cognito (e.g., SOFTWARE_TOKEN_MFA_CODE).",
    )


class CognitoMfaSetupIn(BaseModel):
    session: str
    label: Optional[str] = Field(None, description="Optional label for the authenticator app")


class CognitoMfaVerifyIn(BaseModel):
    email: EmailStr
    session: str
    code: constr(min_length=6, max_length=10)
    friendly_name: Optional[str] = None


class CognitoAuthResponse(BaseModel):
    status: Literal["OK", "CHALLENGE"]
    message: Optional[str] = None
    next_step: Optional[
        Literal[
            "MFA_SETUP",
            "SOFTWARE_TOKEN_MFA",
            "NEW_PASSWORD_REQUIRED",
            "CUSTOM_CHALLENGE",
            "UNKNOWN",
        ]
    ] = None
    challenge_name: Optional[str] = None
    session: Optional[str] = None
    tokens: Optional[CognitoTokens] = None


class CognitoSecretOut(BaseModel):
    secret_code: str
    session: Optional[str] = None
    otpauth_uri: Optional[str] = None


class CognitoMessage(BaseModel):
    status: str = "OK"
    message: Optional[str] = None


