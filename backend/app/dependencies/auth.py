# app/dependencies/auth.py
"""Authentication dependencies for Cognito-backed FastAPI routes."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.auth.identity import Identity
from app.models.user import User


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )
def get_current_user(request: Request) -> User:
    """
    Retrieve the authenticated user from request state.

    The identity middleware verifies the Cognito token and attaches the
    database user. This dependency simply enforces that a valid, active user
    exists for the current request.
    """
    user = getattr(request.state, "user", None)
    if user is None:
        raise _unauthorized("Cognito authentication required")
    if not getattr(user, "is_active", True):
        raise _unauthorized("User is inactive")
    return user


def get_identity(request: Request) -> Identity:
    """
    Get the current request's Identity object.

    This is a lightweight dependency that returns the identity set by the
    identity middleware after Cognito verification.

    Returns Identity.unauthenticated() if no auth succeeded.

    Use this when you need to inspect identity without requiring authentication.
    For protected endpoints, continue using get_current_user.
    """
    identity = getattr(request.state, "identity", None)
    if identity is None:
        return Identity.unauthenticated()
    return identity


def get_current_user_db(request: Request) -> User | None:
    """
    Get the current DB user if authenticated (via either auth method).

    Returns None if not authenticated. Does not raise exceptions.
    Useful for optional authentication scenarios.
    """
    return getattr(request.state, "user", None)