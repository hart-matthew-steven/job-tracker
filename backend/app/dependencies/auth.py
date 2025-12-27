# app/dependencies/auth.py
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import verify_token_purpose
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
        payload = verify_token_purpose(creds.credentials, expected_purpose="access")
    except ValueError:
        raise _unauthorized("Invalid or expired token")
    except JWTError:
        raise _unauthorized("Invalid or expired token")

    email = str(payload.get("sub") or "").strip().lower()
    if not email:
        raise _unauthorized("Invalid or expired token")

    token_version = int(payload.get("ver") or 0)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise _unauthorized("User not found")
    if not getattr(user, "is_active", True):
        raise _unauthorized("User is inactive")
    if int(getattr(user, "token_version", 0) or 0) != token_version:
        raise _unauthorized("Invalid or expired token")

    return user