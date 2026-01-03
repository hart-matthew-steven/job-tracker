# tests/test_cognito_verifier.py
"""
Unit tests for Cognito JWT verification module.

These tests do NOT require real Cognito access:
- JWKS responses are mocked
- Test tokens are generated locally with known keys
- Cache TTL behavior is tested via time mocking
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import pytest
from jose import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


# ---------------------------------------------------------------------------
# Test key generation helpers
# ---------------------------------------------------------------------------


def generate_rsa_key_pair():
    """Generate an RSA key pair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend(),
    )
    return private_key


def private_key_to_pem(private_key) -> bytes:
    """Convert private key to PEM format."""
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def public_key_to_jwk(private_key, kid: str) -> dict:
    """Convert public key to JWK format for JWKS mock."""
    public_key = private_key.public_key()
    public_numbers = public_key.public_numbers()

    import base64

    def int_to_base64url(n: int, length: int) -> str:
        return base64.urlsafe_b64encode(n.to_bytes(length, "big")).decode("utf-8").rstrip("=")

    return {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": int_to_base64url(public_numbers.n, 256),
        "e": int_to_base64url(public_numbers.e, 3),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def test_key_pair():
    """Generate a test RSA key pair."""
    return generate_rsa_key_pair()


@pytest.fixture
def test_kid():
    """Test key ID."""
    return "test-kid-12345"


@pytest.fixture
def test_issuer():
    """Test Cognito issuer URL."""
    return "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TestPool"


@pytest.fixture
def test_client_id():
    """Test Cognito app client ID."""
    return "test-client-id-abc123"


@pytest.fixture
def mock_settings(test_issuer, test_client_id):
    """Patch settings with test Cognito configuration."""
    with patch("app.auth.cognito.settings") as mock:
        mock.COGNITO_REGION = "us-east-1"
        mock.COGNITO_USER_POOL_ID = "us-east-1_TestPool"
        mock.COGNITO_APP_CLIENT_ID = test_client_id
        mock.COGNITO_JWKS_CACHE_SECONDS = 900
        mock.cognito_issuer = test_issuer
        mock.cognito_jwks_url = f"{test_issuer}/.well-known/jwks.json"
        yield mock


@pytest.fixture
def mock_jwks_response(test_key_pair, test_kid):
    """Create a mock JWKS response."""
    jwk = public_key_to_jwk(test_key_pair, test_kid)
    return {"keys": [jwk]}


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear JWKS cache before each test."""
    from app.auth.cognito import clear_jwks_cache

    clear_jwks_cache()
    yield
    clear_jwks_cache()


# ---------------------------------------------------------------------------
# Token generation helpers
# ---------------------------------------------------------------------------


def create_test_token(
    private_key,
    kid: str,
    issuer: str,
    client_id: str,
    token_use: str = "access",
    sub: str = "test-user-id",
    email: str = "test@example.com",
    exp_offset: int = 3600,  # 1 hour from now
    extra_claims: dict | None = None,
) -> str:
    """Create a test JWT signed with the given private key."""
    now = int(time.time())
    claims = {
        "sub": sub,
        "iss": issuer,
        "token_use": token_use,
        "iat": now,
        "exp": now + exp_offset,
        "email": email,
    }

    if token_use == "access":
        claims["client_id"] = client_id
    else:  # id token
        claims["aud"] = client_id

    if extra_claims:
        claims.update(extra_claims)

    pem = private_key_to_pem(private_key)
    return jwt.encode(claims, pem, algorithm="RS256", headers={"kid": kid})


# ---------------------------------------------------------------------------
# Tests: Successful verification
# ---------------------------------------------------------------------------


def test_verify_access_token_success(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer, test_client_id
):
    """Test successful verification of a valid access token."""
    from app.auth.cognito import verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        test_client_id,
        token_use="access",
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        claims = verify_cognito_jwt(token)

        assert claims["sub"] == "test-user-id"
        assert claims["email"] == "test@example.com"
        assert claims["token_use"] == "access"
        assert claims["iss"] == test_issuer
        assert claims["client_id"] == test_client_id


def test_verify_id_token_success(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer, test_client_id
):
    """Test successful verification of a valid ID token."""
    from app.auth.cognito import verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        test_client_id,
        token_use="id",
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        claims = verify_cognito_jwt(token)

        assert claims["sub"] == "test-user-id"
        assert claims["token_use"] == "id"
        assert claims["aud"] == test_client_id


# ---------------------------------------------------------------------------
# Tests: Verification failures
# ---------------------------------------------------------------------------


def test_expired_token_raises_error(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer, test_client_id
):
    """Test that expired tokens raise CognitoTokenExpiredError."""
    from app.auth.cognito import CognitoTokenExpiredError, verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        test_client_id,
        exp_offset=-3600,  # Already expired
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with pytest.raises(CognitoTokenExpiredError):
            verify_cognito_jwt(token)


def test_wrong_issuer_raises_error(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_client_id
):
    """Test that tokens with wrong issuer raise CognitoIssuerMismatchError."""
    from app.auth.cognito import CognitoIssuerMismatchError, verify_cognito_jwt

    wrong_issuer = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_WrongPool"
    token = create_test_token(
        test_key_pair,
        test_kid,
        wrong_issuer,  # Wrong issuer
        test_client_id,
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with pytest.raises(CognitoIssuerMismatchError):
            verify_cognito_jwt(token)


def test_wrong_client_id_access_token_raises_error(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer
):
    """Test that access tokens with wrong client_id raise CognitoAudienceMismatchError."""
    from app.auth.cognito import CognitoAudienceMismatchError, verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        "wrong-client-id",  # Wrong client ID
        token_use="access",
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with pytest.raises(CognitoAudienceMismatchError):
            verify_cognito_jwt(token)


def test_wrong_audience_id_token_raises_error(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer
):
    """Test that ID tokens with wrong aud raise CognitoAudienceMismatchError."""
    from app.auth.cognito import CognitoAudienceMismatchError, verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        "wrong-audience",  # Wrong audience
        token_use="id",
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with pytest.raises(CognitoAudienceMismatchError):
            verify_cognito_jwt(token)


def test_invalid_signature_raises_error(mock_settings, mock_jwks_response, test_kid, test_issuer, test_client_id):
    """Test that tokens signed with wrong key raise CognitoInvalidSignatureError."""
    from app.auth.cognito import CognitoInvalidSignatureError, verify_cognito_jwt

    # Create token with a different key than what's in JWKS
    different_key = generate_rsa_key_pair()
    token = create_test_token(
        different_key,
        test_kid,  # Same kid but different key
        test_issuer,
        test_client_id,
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        with pytest.raises(CognitoInvalidSignatureError):
            verify_cognito_jwt(token)


def test_missing_kid_raises_error(mock_settings, test_issuer, test_client_id):
    """Test that tokens without kid in header raise CognitoInvalidTokenError."""
    from app.auth.cognito import CognitoInvalidTokenError, verify_cognito_jwt

    # Create a malformed token without kid
    import base64

    header = base64.urlsafe_b64encode(b'{"alg":"RS256","typ":"JWT"}').decode().rstrip("=")
    payload = base64.urlsafe_b64encode(b'{"sub":"test"}').decode().rstrip("=")
    token = f"{header}.{payload}.fake_signature"

    with pytest.raises(CognitoInvalidTokenError, match="missing 'kid'"):
        verify_cognito_jwt(token)


# ---------------------------------------------------------------------------
# Tests: JWKS caching
# ---------------------------------------------------------------------------


def test_jwks_is_cached(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer, test_client_id
):
    """Test that JWKS is fetched once and cached for subsequent verifications."""
    from app.auth.cognito import verify_cognito_jwt

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        test_client_id,
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # First verification
        verify_cognito_jwt(token)
        assert mock_urlopen.call_count == 1

        # Second verification should use cache
        verify_cognito_jwt(token)
        assert mock_urlopen.call_count == 1  # Still 1, not 2


def test_jwks_cache_expires(
    mock_settings, mock_jwks_response, test_key_pair, test_kid, test_issuer, test_client_id
):
    """Test that JWKS cache expires after TTL."""
    from app.auth.cognito import verify_cognito_jwt

    # Set very short TTL for testing
    mock_settings.COGNITO_JWKS_CACHE_SECONDS = 1

    token = create_test_token(
        test_key_pair,
        test_kid,
        test_issuer,
        test_client_id,
    )

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_jwks_response).encode()
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        # First verification
        verify_cognito_jwt(token)
        assert mock_urlopen.call_count == 1

        # Wait for cache to expire
        time.sleep(1.1)

        # Should refetch
        verify_cognito_jwt(token)
        assert mock_urlopen.call_count == 2


# ---------------------------------------------------------------------------
# Tests: Configuration errors
# ---------------------------------------------------------------------------


def test_not_configured_raises_error():
    """Test that missing Cognito config raises CognitoNotConfiguredError."""
    from app.auth.cognito import CognitoNotConfiguredError, verify_cognito_jwt

    with patch("app.auth.cognito.settings") as mock:
        mock.cognito_issuer = ""
        mock.COGNITO_APP_CLIENT_ID = ""

        with pytest.raises(CognitoNotConfiguredError):
            verify_cognito_jwt("any.token.here")


def test_jwks_fetch_failure_raises_error(mock_settings):
    """Test that JWKS fetch failures raise CognitoJWKSFetchError."""
    from app.auth.cognito import CognitoJWKSFetchError, _jwks_cache

    with patch("app.auth.cognito.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = Exception("Network error")

        with pytest.raises(CognitoJWKSFetchError, match="Network error"):
            _jwks_cache.get_signing_key("any-kid")

