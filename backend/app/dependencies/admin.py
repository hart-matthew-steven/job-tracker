from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User


def require_admin_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    Ensure the authenticated user has admin privileges.
    """

    db_user = db.query(User).filter(User.id == current_user.id).first()
    if db_user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not db_user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return db_user
