# app/auth/identity.py
"""
Canonical authenticated identity model.

This module provides a unified representation of an authenticated user backed
by Amazon Cognito. Downstream code can reason about “who is this user?” without
inspecting raw JWTs or Cognito payloads.

The Identity object is INTERNAL ONLY and should not be returned directly
to clients. It's used for authorization decisions and audit logging.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Identity:
    """
    Canonical representation of an authenticated (or unauthenticated) user.

    Attributes:
        user_id: Internal application user ID. For Cognito users without a linked
                 account, this is a temporary synthetic ID like ``cognito:{sub}``.
        auth_provider: Currently always ``"cognito"`` (or ``None`` if unauthenticated).
        external_subject: The Cognito ``sub`` claim. This is stable across sessions
                          and can be used to link Cognito accounts to internal users.
        email: User's email address if available.
        is_authenticated: True if the user has been successfully authenticated.
        raw_claims: Optional dict of raw token claims for debugging/audit.
                    Should NOT be used for authorization decisions.
    """

    user_id: str | None = None
    auth_provider: str | None = None  # "cognito" | None
    external_subject: str | None = None  # Cognito `sub`
    email: str | None = None
    is_authenticated: bool = False
    raw_claims: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def unauthenticated(cls) -> Identity:
        """Create an identity representing an unauthenticated request."""
        return cls(
            user_id=None,
            auth_provider=None,
            external_subject=None,
            email=None,
            is_authenticated=False,
            raw_claims={},
        )

    @classmethod
    def from_cognito(
        cls,
        sub: str,
        email: str | None = None,
        raw_claims: dict[str, Any] | None = None,
        linked_user_id: str | None = None,
    ) -> Identity:
        """
        Create an identity from Cognito authentication.

        Args:
            sub: The Cognito `sub` claim (stable user identifier).
            email: User's email from Cognito claims (if present).
            raw_claims: Full Cognito token claims for debugging.
            linked_user_id: If the Cognito account is linked to an internal
                            user, pass the internal user ID here. Otherwise,
                            a synthetic ID is generated.
        """
        # If no linked internal user, use a synthetic deterministic ID
        user_id = linked_user_id if linked_user_id else f"cognito:{sub}"

        return cls(
            user_id=user_id,
            auth_provider="cognito",
            external_subject=sub,
            email=email.strip().lower() if email else None,
            is_authenticated=True,
            raw_claims=raw_claims or {},
        )

    def to_debug_dict(self) -> dict[str, Any]:
        """
        Return a safe subset of identity info for debug endpoints.

        Does NOT include raw_claims to avoid leaking sensitive data.
        """
        return {
            "user_id": self.user_id,
            "auth_provider": self.auth_provider,
            "external_subject": self.external_subject,
            "email": self.email,
            "is_authenticated": self.is_authenticated,
        }

