from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.services.turnstile import TurnstileVerificationError
from app.main import app


def _override_db(db_session):
    app.dependency_overrides[get_db] = lambda: db_session


def _reset_overrides():
    app.dependency_overrides.clear()


def test_signup_requires_confirmation(monkeypatch):
    monkeypatch.setattr("app.routes.auth_cognito.verify_turnstile_token", lambda *a, **k: None)
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SITE_KEY", "site")
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr("app.routes.auth_cognito.cognito_sign_up", lambda *a, **k: {"UserConfirmed": False})

    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/signup",
            json={
                "email": "user@example.com",
                "password": "Password12345!",
                "name": "Test User",
                "turnstile_token": "token123",
            },
        )
    assert resp.status_code == 200
    assert resp.json()["status"] == "CONFIRMATION_REQUIRED"


def test_signup_rejects_without_turnstile_token():
    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/signup",
            json={"email": "user@example.com", "password": "Password12345!", "name": "Test User"},
        )
    assert resp.status_code == 422


def test_signup_rejects_when_turnstile_fails(monkeypatch):
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SITE_KEY", "site")
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SECRET_KEY", "secret")

    def _raise(*args, **kwargs):
        raise TurnstileVerificationError("nope")

    monkeypatch.setattr("app.routes.auth_cognito.verify_turnstile_token", _raise)

    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/signup",
            json={
                "email": "user@example.com",
                "password": "Password12345!",
                "name": "Test User",
                "turnstile_token": "token123",
            },
        )
    assert resp.status_code == 400
    assert "CAPTCHA" in resp.json()["message"]


def test_signup_fail_closed_when_turnstile_not_configured(monkeypatch):
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SITE_KEY", "")
    monkeypatch.setattr("app.routes.auth_cognito.settings.TURNSTILE_SECRET_KEY", "")

    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/signup",
            json={
                "email": "user@example.com",
                "password": "Password12345!",
                "name": "Test User",
                "turnstile_token": "token123",
            },
        )
    assert resp.status_code == 503
    assert "temporarily unavailable" in resp.json()["message"]


def test_login_ok(monkeypatch, db_session):
    _override_db(db_session)

    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_initiate_auth",
        lambda email, password: {
            "AuthenticationResult": {
                "AccessToken": "ACCESS",
                "IdToken": "IDTOKEN",
                "RefreshToken": "REFRESH",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        },
    )
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_get_user",
        lambda access_token: {"sub": "abc123", "email": "login@example.com", "name": "Login User"},
    )

    try:
        with TestClient(app) as c:
            resp = c.post(
                "/auth/cognito/login",
                json={"email": "login@example.com", "password": "Password12345!"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert data["tokens"]["access_token"]
    finally:
        _reset_overrides()


def test_login_returns_challenge(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_initiate_auth",
        lambda email, password: {
            "ChallengeName": "SOFTWARE_TOKEN_MFA",
            "Session": "session123",
            "ChallengeParameters": {"foo": "bar"},
        },
    )

    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/login",
            json={"email": "login@example.com", "password": "Password12345!"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CHALLENGE"
    assert data["challenge_name"] == "SOFTWARE_TOKEN_MFA"
    assert data["next_step"] == "SOFTWARE_TOKEN_MFA"
    assert data["session"] == "session123"


def test_login_returns_mfa_setup_challenge(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_initiate_auth",
        lambda email, password: {
            "ChallengeName": "MFA_SETUP",
            "Session": "session_setup",
        },
    )

    with TestClient(app) as c:
        resp = c.post(
            "/auth/cognito/login",
            json={"email": "login@example.com", "password": "Password12345!"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CHALLENGE"
    assert data["challenge_name"] == "MFA_SETUP"
    assert data["next_step"] == "MFA_SETUP"
    assert data["session"] == "session_setup"


def test_challenge_flow_success(monkeypatch, db_session):
    _override_db(db_session)

    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_respond_to_challenge",
        lambda session, challenge_name, responses: {
            "AuthenticationResult": {
                "AccessToken": "ACCESS",
                "IdToken": "IDTOKEN",
                "RefreshToken": "REFRESH",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        },
    )
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_get_user",
        lambda access_token: {"sub": "xyz789", "email": "challenge@example.com", "name": "Challenge User"},
    )

    payload = {
        "email": "challenge@example.com",
        "challenge_name": "SOFTWARE_TOKEN_MFA",
        "session": "session123",
        "responses": {"SOFTWARE_TOKEN_MFA_CODE": "123456"},
    }

    try:
        with TestClient(app) as c:
            resp = c.post("/auth/cognito/challenge", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert data["tokens"]["access_token"]
    finally:
        _reset_overrides()


def test_mfa_setup(monkeypatch):
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_associate_software_token",
        lambda **kwargs: {"SecretCode": "ABCDEF", "Session": "session456"},
    )

    with TestClient(app) as c:
        resp = c.post("/auth/cognito/mfa/setup", json={"session": "session123"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["secret_code"] == "ABCDEF"
    assert data["session"] == "session456"
    assert data["otpauth_uri"].startswith("otpauth://")


def test_mfa_verify(monkeypatch, db_session):
    _override_db(db_session)

    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_verify_software_token",
        lambda code, session=None, friendly_name=None, access_token=None: {"Status": "SUCCESS", "Session": "sess2"},
    )
    respond_calls = {}

    def _fake_respond(session, challenge_name, responses):
        respond_calls["session"] = session
        respond_calls["challenge_name"] = challenge_name
        respond_calls["responses"] = responses
        return {"AuthenticationResult": {"AccessToken": "ACCESS"}}

    monkeypatch.setattr("app.routes.auth_cognito.cognito_respond_to_challenge", _fake_respond)
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_get_user",
        lambda access_token: {"sub": "totp123", "email": "mfa@example.com", "name": "MFA User"},
    )

    payload = {
        "email": "mfa@example.com",
        "session": "session123",
        "code": "123456",
    }

    try:
        with TestClient(app) as c:
            resp = c.post("/auth/cognito/mfa/verify", json=payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "OK"
        assert respond_calls["challenge_name"] == "MFA_SETUP"
        assert respond_calls["responses"] == {"USERNAME": "mfa@example.com", "ANSWER": "SUCCESS"}
    finally:
        _reset_overrides()


def test_refresh_returns_tokens(monkeypatch, db_session):
    _override_db(db_session)

    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_refresh_auth",
        lambda refresh_token: {
            "AuthenticationResult": {
                "AccessToken": "NEW_ACCESS",
                "IdToken": "NEW_ID",
                "ExpiresIn": 3600,
                "TokenType": "Bearer",
            }
        },
    )
    monkeypatch.setattr(
        "app.routes.auth_cognito.cognito_get_user",
        lambda access_token: {"sub": "refresh123", "email": "refresh@example.com", "name": "Refresh User"},
    )

    try:
        with TestClient(app) as c:
            resp = c.post("/auth/cognito/refresh", json={"refresh_token": "refresh_token_value"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["tokens"]["access_token"] == "NEW_ACCESS"
        # refresh token absent => frontend should reuse previous one
        assert data["tokens"]["refresh_token"] == "refresh_token_value"
    finally:
        _reset_overrides()


