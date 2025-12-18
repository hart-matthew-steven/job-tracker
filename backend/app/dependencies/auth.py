# app/dependencies/auth.py
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import get_token_subject
from app.core.database import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates:
      - Authorization: Bearer <token>
      - token signature + exp
      - user exists + is_active
    Returns:
      - User SQLAlchemy model
    """
    if not creds or creds.scheme.lower() != "bearer":
        raise _unauthorized("Missing Authorization header")

    try:
        email = get_token_subject(creds.credentials)
    except (JWTError, ValueError):
        raise _unauthorized("Invalid or expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise _unauthorized("User not found")
    if not getattr(user, "is_active", True):
        raise _unauthorized("User is inactive")

    return user