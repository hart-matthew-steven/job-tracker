from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth.identity import Identity
from app.core.config import settings
from app.core.database import SessionLocal
from app.services.cognito_client import CognitoClientError, cognito_get_user
from app.services.users import ensure_cognito_user, get_user_by_cognito_sub

logger = logging.getLogger(__name__)

AUTH_BYPASS_PATHS = frozenset(
    [
        "/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
)

AUTH_BYPASS_PREFIXES = (
    "/auth/cognito",  # Public Cognito API routes
    "/auth/debug",  # Explicitly gated debug endpoints (dev-only)
)


def _is_auth_bypass_path(path: str) -> bool:
    """Check if a path should bypass authentication."""
    path = path.rstrip("/")
    if path in AUTH_BYPASS_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in AUTH_BYPASS_PREFIXES)


def _is_guard_duty_callback(request: Request) -> bool:
    """
    Allow GuardDuty scan callbacks (which authenticate via shared secret at the route layer)
    to skip Cognito verification. The route itself still enforces DOC_SCAN_SHARED_SECRET.
    """
    if request.method.upper() != "POST":
        return False

    path = request.url.path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) != 5:
        return False
    if parts[0] != "jobs" or parts[2] != "documents" or parts[4] != "scan-result":
        return False
    try:
        int(parts[1])
        int(parts[3])
    except ValueError:
        return False
    return True


def register_identity_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def identity_middleware(request: Request, call_next):
        """
        Enforce Cognito authentication for all protected routes.

        Requests must include a Cognito access token in the Authorization header.
        Tokens are verified against the User Pool JWKS and mapped to an internal
        user record. The resulting identity is stored on request.state.
        """
        request.state.identity = Identity.unauthenticated()
        request.state.user = None
        request.state.cognito_claims = None

        # Allow CORS preflight to flow through CORSMiddleware unchanged
        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/")
        if _is_auth_bypass_path(path):
            return await call_next(request)
        if _is_guard_duty_callback(request):
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "UNAUTHORIZED",
                    "message": "Authorization header with Bearer token required",
                },
            )

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "UNAUTHORIZED",
                    "message": "Authorization header with Bearer token required",
                },
            )

        from app.auth.cognito import (
            CognitoInvalidTokenError,
            CognitoTokenExpiredError,
            CognitoVerificationError,
            verify_cognito_jwt,
        )

        try:
            claims = verify_cognito_jwt(token)
        except CognitoTokenExpiredError:
            logger.info("Cognito access token expired")
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Access token has expired"},
            )
        except CognitoInvalidTokenError:
            logger.warning("Rejected invalid Cognito token")
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Invalid access token"},
            )
        except CognitoVerificationError as exc:
            logger.warning("Cognito verification failed: %s", exc)
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Invalid access token"},
            )

        request.state.cognito_claims = claims
        if claims.get("token_use") != "access":
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Access token required"},
            )

        cognito_sub = claims.get("sub")
        if not cognito_sub:
            return JSONResponse(
                status_code=401,
                content={"error": "UNAUTHORIZED", "message": "Token missing subject"},
            )

        db = SessionLocal()
        try:
            user = get_user_by_cognito_sub(db, cognito_sub)
            if user is None:
                email = (claims.get("email") or "").strip().lower()
                name = claims.get("name")

                if not email:
                    try:
                        attributes = cognito_get_user(token)
                    except CognitoClientError as exc:
                        logger.error("Cannot fetch Cognito profile for %s: %s", cognito_sub, exc)
                        return JSONResponse(
                            status_code=401,
                            content={
                                "error": "UNAUTHORIZED",
                                "message": "Unable to resolve Cognito account",
                            },
                        )
                    email = (attributes.get("email") or "").strip().lower()
                    name = name or attributes.get("name") or attributes.get("Username")

                if not email:
                    logger.error("Cognito subject %s missing email attribute; cannot provision", cognito_sub)
                    return JSONResponse(
                        status_code=500,
                        content={
                            "error": "INTERNAL_ERROR",
                            "message": "Cognito user profile missing required attributes",
                        },
                    )

                user = ensure_cognito_user(
                    db,
                    cognito_sub=cognito_sub,
                    email=email,
                    name=name,
                )

            if not getattr(user, "is_active", True):
                return JSONResponse(
                    status_code=403,
                    content={"error": "FORBIDDEN", "message": "User is inactive"},
                )

            request.state.user = user
            request.state.identity = Identity.from_cognito(
                sub=cognito_sub,
                email=user.email,
                raw_claims=claims,
                linked_user_id=str(user.id),
            )
        except ValueError as exc:
            logger.error("Cognito user provisioning failed: %s", exc)
            return JSONResponse(
                status_code=409,
                content={"error": "CONFLICT", "message": str(exc)},
            )
        finally:
            db.close()

        return await call_next(request)

