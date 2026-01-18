# app/services/users.py
"""
User management helpers.

Responsibilities:
- JIT (Just-In-Time) user provisioning for Cognito-authenticated users
- User lookup by cognito_sub or email
- Normalizing Cognito attributes before persisting
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.user import User

logger = logging.getLogger(__name__)

DEFAULT_COGNITO_NAME = "Cognito User"


def get_user_by_cognito_sub(db: Session, cognito_sub: str) -> Optional[User]:
    """Look up a user by their Cognito subject identifier."""
    return db.query(User).filter(User.cognito_sub == cognito_sub).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Look up a user by email address."""
    return db.query(User).filter(User.email == email.strip().lower()).first()


def get_user_by_stripe_customer_id(db: Session, customer_id: str) -> Optional[User]:
    """Look up a user by their linked Stripe customer id."""
    if not customer_id:
        return None
    return db.query(User).filter(User.stripe_customer_id == customer_id).first()


def provision_cognito_user(
    db: Session,
    cognito_sub: str,
    email: str,
    *,
    name: str | None = None,
) -> User:
    """
    Create a new Cognito-backed user in the database.

    This is called on the first successful Cognito-authenticated request
    when no existing user is found.

    Args:
        db: Database session
        cognito_sub: Cognito `sub` claim (immutable identifier)
        email: User's email from Cognito claims

    Returns:
        The newly created User

    Raises:
        ValueError: If cognito_sub or email is empty
    """
    if not cognito_sub:
        raise ValueError("cognito_sub is required")
    if not email:
        raise ValueError("email is required")

    normalized_email = email.strip().lower()
    normalized_name = normalize_name(name, fallback=normalized_email)

    user = User(
        email=normalized_email,
        name=normalized_name,
        cognito_sub=cognito_sub,
        auth_provider="cognito",
        is_active=True,
        is_email_verified=False,
        email_verified_at=None,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(
        "Provisioned new Cognito user: id=%s, cognito_sub=%s, email=%s",
        user.id,
        cognito_sub,
        normalized_email,
    )

    return user


def ensure_cognito_user(
    db: Session,
    *,
    cognito_sub: str,
    email: str,
    name: str | None = None,
) -> User:
    """
    Ensure a database user exists for a Cognito-authenticated identity.

    This is idempotent: if a user already exists, it's returned as-is.
    If no user exists, a new one is provisioned (JIT provisioning).

    Args:
        db: Database session
        cognito_sub: Cognito subject identifier
        email: Email address from Cognito claims
        name: Optional name from Cognito attributes

    Returns:
        User: existing or newly created user
    """
    if not cognito_sub:
        raise ValueError("cognito_sub is required")
    if not email:
        raise ValueError("email is required")

    user = get_user_by_cognito_sub(db, cognito_sub)
    if user:
        return user

    existing_by_email = get_user_by_email(db, email)
    if existing_by_email:
        # Safe default: prevent automatic linking until explicit feature lands
        raise ValueError(
            f"A user with email {email} already exists. "
            "Please contact support to link your accounts."
        )

    return provision_cognito_user(
        db=db,
        cognito_sub=cognito_sub,
        email=email,
        name=name,
    )


def normalize_name(name: str | None, fallback: str) -> str:
    """Normalize name, falling back to email/localpart if needed."""
    if name:
        clean = name.strip()
        if clean:
            return clean[:100]

    # Fallback: use email local part or default string
    if fallback and "@" in fallback:
        local = fallback.split("@", 1)[0]
        if local:
            return local[:100]
    return DEFAULT_COGNITO_NAME


