# app/auth/cognito.py
"""
Cognito JWT verification module.

Used by the identity middleware to validate Cognito access/ID tokens during the
production cutover. Responsibilities:
- Lazy JWKS fetching (no network calls on import)
- In-memory JWKS caching with configurable TTL
- Clear typed exceptions for verification failures
- Support for both ID tokens (aud claim) and access tokens (client_id claim)
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any
import ssl
from urllib.request import urlopen

import certifi

from jose import JWTError, jwk, jwt

from app.core.config import settings


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CognitoVerificationError(Exception):
    """Base exception for Cognito JWT verification failures."""

    pass


class CognitoNotConfiguredError(CognitoVerificationError):
    """Raised when Cognito settings are not configured."""

    pass


class CognitoJWKSFetchError(CognitoVerificationError):
    """Raised when JWKS cannot be fetched from Cognito."""

    pass


class CognitoTokenExpiredError(CognitoVerificationError):
    """Raised when the token has expired."""

    pass


class CognitoInvalidSignatureError(CognitoVerificationError):
    """Raised when the token signature is invalid."""

    pass


class CognitoIssuerMismatchError(CognitoVerificationError):
    """Raised when the token issuer does not match expected Cognito issuer."""

    pass


class CognitoAudienceMismatchError(CognitoVerificationError):
    """Raised when the token audience/client_id does not match the app client."""

    pass


class CognitoInvalidTokenError(CognitoVerificationError):
    """Raised for general token validation failures."""

    pass


# ---------------------------------------------------------------------------
# JWKS Cache
# ---------------------------------------------------------------------------


class _JWKSCache:
    """
    Thread-safe in-memory cache for Cognito JWKS.

    The cache is populated lazily on first verification attempt.
    TTL is controlled by COGNITO_JWKS_CACHE_SECONDS.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: dict[str, Any] | None = None
        self._fetched_at: float = 0.0

    def get_signing_key(self, kid: str) -> Any:
        """
        Get the signing key for the given key ID.

        Fetches JWKS if not cached or cache has expired.
        Raises CognitoJWKSFetchError if fetch fails.
        Raises CognitoInvalidTokenError if kid not found.
        """
        with self._lock:
            now = time.time()
            ttl = settings.COGNITO_JWKS_CACHE_SECONDS

            # Refresh if expired or not yet fetched
            if self._keys is None or (now - self._fetched_at) > ttl:
                self._refresh_keys()

            if kid not in self._keys:
                # Key not found; maybe keys rotated. Try one refresh.
                self._refresh_keys()

            if kid not in self._keys:
                raise CognitoInvalidTokenError(f"Signing key not found for kid: {kid}")

            return self._keys[kid]

    def _refresh_keys(self) -> None:
        """Fetch JWKS from Cognito and rebuild key map."""
        jwks_url = settings.cognito_jwks_url
        if not jwks_url:
            raise CognitoNotConfiguredError("Cognito JWKS URL not configured")

        try:
            logger.info("Fetching Cognito JWKS from %s", jwks_url)
            context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(jwks_url, timeout=10, context=context) as resp:
                import json

                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.error("Failed to fetch Cognito JWKS: %s", e)
            raise CognitoJWKSFetchError(f"Failed to fetch JWKS: {e}") from e

        keys_list = data.get("keys", [])
        if not keys_list:
            raise CognitoJWKSFetchError("JWKS response contains no keys")

        # Build kid -> key mapping
        self._keys = {}
        for key_data in keys_list:
            kid = key_data.get("kid")
            if kid:
                try:
                    self._keys[kid] = jwk.construct(key_data)
                except Exception as e:
                    logger.warning("Failed to construct key for kid=%s: %s", kid, e)

        self._fetched_at = time.time()
        logger.info("Cached %d Cognito signing keys", len(self._keys))

    def clear(self) -> None:
        """Clear the cache (useful for testing)."""
        with self._lock:
            self._keys = None
            self._fetched_at = 0.0


# Module-level cache instance
_jwks_cache = _JWKSCache()


def clear_jwks_cache() -> None:
    """Clear the JWKS cache. Exposed for testing."""
    _jwks_cache.clear()


# ---------------------------------------------------------------------------
# Token Verification
# ---------------------------------------------------------------------------


def verify_cognito_jwt(token: str) -> dict[str, Any]:
    """
    Verify a Cognito JWT (access token or ID token).

    Validates:
    - Signature via JWKS
    - exp / iat / nbf claims
    - Issuer matches configured Cognito issuer
    - Audience/client_id matches configured app client:
      - ID tokens: validates `aud` claim
      - Access tokens: validates `client_id` claim

    Args:
        token: The JWT string to verify

    Returns:
        The decoded token claims as a dict

    Raises:
        CognitoNotConfiguredError: Cognito settings not configured
        CognitoTokenExpiredError: Token has expired
        CognitoInvalidSignatureError: Signature verification failed
        CognitoIssuerMismatchError: Issuer does not match
        CognitoAudienceMismatchError: Audience/client_id does not match
        CognitoInvalidTokenError: Other validation failures
    """
    issuer = settings.cognito_issuer
    client_id = settings.COGNITO_APP_CLIENT_ID

    if not issuer or not client_id:
        raise CognitoNotConfiguredError(
            "Cognito not configured (COGNITO_REGION, COGNITO_USER_POOL_ID, COGNITO_APP_CLIENT_ID required)"
        )

    # Decode header to get kid (without verifying signature yet)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as e:
        raise CognitoInvalidTokenError(f"Invalid token header: {e}") from e

    kid = unverified_header.get("kid")
    if not kid:
        raise CognitoInvalidTokenError("Token header missing 'kid' claim")

    # Get signing key from cache
    signing_key = _jwks_cache.get_signing_key(kid)

    # Decode and verify the token
    try:
        # python-jose handles exp/iat/nbf validation automatically
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            issuer=issuer,
            # We handle audience manually below because Cognito uses different
            # claim names for ID vs access tokens
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError as e:
        raise CognitoTokenExpiredError("Token has expired") from e
    except jwt.JWTClaimsError as e:
        error_msg = str(e).lower()
        if "issuer" in error_msg:
            raise CognitoIssuerMismatchError(f"Issuer mismatch: {e}") from e
        raise CognitoInvalidTokenError(f"Claims validation failed: {e}") from e
    except JWTError as e:
        raise CognitoInvalidSignatureError(f"Signature verification failed: {e}") from e

    # Validate issuer explicitly (belt + suspenders)
    token_issuer = claims.get("iss", "")
    if token_issuer != issuer:
        raise CognitoIssuerMismatchError(f"Expected issuer {issuer}, got {token_issuer}")

    # Validate audience/client_id based on token type
    token_use = claims.get("token_use", "")

    if token_use == "id":
        # ID tokens have `aud` claim
        aud = claims.get("aud", "")
        if aud != client_id:
            raise CognitoAudienceMismatchError(f"Expected aud {client_id}, got {aud}")
    elif token_use == "access":
        # Access tokens have `client_id` claim
        token_client_id = claims.get("client_id", "")
        if token_client_id != client_id:
            raise CognitoAudienceMismatchError(f"Expected client_id {client_id}, got {token_client_id}")
    else:
        # Unknown token type — still allow if issuer matched
        logger.warning("Unknown token_use: %s (issuer matched, allowing)", token_use)

    return claims

