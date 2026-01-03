# tests/test_identity.py
"""
Unit tests for the Identity model and auth identity mapping.

These tests verify:
- Cognito identity mapping
- Unauthenticated identity handling
- Identity debug output safety

Tests do NOT require real Cognito or database access.
"""
from __future__ import annotations

import pytest

from app.auth.identity import Identity


# ---------------------------------------------------------------------------
# Tests: Identity.unauthenticated()
# ---------------------------------------------------------------------------


def test_unauthenticated_identity():
    """Test that unauthenticated identity has correct defaults."""
    identity = Identity.unauthenticated()

    assert identity.user_id is None
    assert identity.auth_provider is None
    assert identity.external_subject is None
    assert identity.email is None
    assert identity.is_authenticated is False
    assert identity.raw_claims == {}


def test_unauthenticated_to_debug_dict():
    """Test debug output for unauthenticated identity."""
    identity = Identity.unauthenticated()
    debug = identity.to_debug_dict()

    assert debug == {
        "user_id": None,
        "auth_provider": None,
        "external_subject": None,
        "email": None,
        "is_authenticated": False,
    }


# ---------------------------------------------------------------------------
# Tests: Identity.from_cognito()
# ---------------------------------------------------------------------------


def test_cognito_identity():
    """Test Cognito identity creation."""
    identity = Identity.from_cognito(
        sub="abc123-def456",
        email="Cognito.User@Example.COM",
        raw_claims={"sub": "abc123-def456", "token_use": "access"},
    )

    assert identity.user_id == "cognito:abc123-def456"  # Synthetic ID
    assert identity.auth_provider == "cognito"
    assert identity.external_subject == "abc123-def456"
    assert identity.email == "cognito.user@example.com"  # Normalized
    assert identity.is_authenticated is True
    assert identity.raw_claims == {"sub": "abc123-def456", "token_use": "access"}


def test_cognito_identity_with_linked_user():
    """Test Cognito identity when linked to internal user."""
    identity = Identity.from_cognito(
        sub="xyz789",
        email="linked@example.com",
        linked_user_id="internal-user-42",
    )

    # When linked, user_id should be the internal ID, not synthetic
    assert identity.user_id == "internal-user-42"
    assert identity.auth_provider == "cognito"
    assert identity.external_subject == "xyz789"


def test_cognito_identity_no_email():
    """Test Cognito identity when email is not present."""
    identity = Identity.from_cognito(
        sub="no-email-user",
        email=None,
    )

    assert identity.user_id == "cognito:no-email-user"
    assert identity.email is None
    assert identity.is_authenticated is True


def test_cognito_to_debug_dict():
    """Test debug output for Cognito identity."""
    identity = Identity.from_cognito(
        sub="debug-test-sub",
        email="test@cognito.com",
        raw_claims={"iss": "https://cognito-idp...", "secret": "token"},
    )
    debug = identity.to_debug_dict()

    # raw_claims should NOT be included
    assert "raw_claims" not in debug
    assert "secret" not in str(debug)
    assert "iss" not in str(debug)  # From raw_claims
    assert debug == {
        "user_id": "cognito:debug-test-sub",
        "auth_provider": "cognito",
        "external_subject": "debug-test-sub",
        "email": "test@cognito.com",
        "is_authenticated": True,
    }


# ---------------------------------------------------------------------------
# Tests: Identity immutability
# ---------------------------------------------------------------------------


def test_identity_is_frozen():
    """Identity dataclass should be immutable."""
    identity = Identity.from_cognito(sub="immutable-test", email="test@example.com")

    with pytest.raises(Exception):
        identity.user_id = "changed"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Tests: get_identity dependency
# ---------------------------------------------------------------------------


def test_get_identity_returns_unauthenticated_when_no_state():
    """Test get_identity fallback when no identity is set."""
    from unittest.mock import MagicMock

    from app.dependencies.auth import get_identity

    # Create a mock request with no identity attribute
    mock_request = MagicMock()
    del mock_request.state.identity  # Ensure it doesn't exist

    identity = get_identity(mock_request)

    assert identity.is_authenticated is False
    assert identity.user_id is None


def test_get_identity_returns_existing_identity():
    """Test get_identity returns the identity from request state."""
    from unittest.mock import MagicMock

    from app.dependencies.auth import get_identity

    expected_identity = Identity.from_cognito(sub="abc123", email="x@y.com")

    mock_request = MagicMock()
    mock_request.state.identity = expected_identity

    identity = get_identity(mock_request)

    assert identity is expected_identity
    assert identity.user_id == "cognito:abc123"

