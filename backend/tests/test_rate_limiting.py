from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from app.core import config as app_config
from app.core.database import get_db


@pytest.mark.usefixtures("_stub_s3")
def test_login_rate_limiting(monkeypatch, db_session):
    """
    Enable SlowAPI rate limiting and ensure /auth/cognito/login returns 429 after exceeding limit.
    """
    import app.core.rate_limit as rate_limit
    import app.routes.auth_cognito as auth_cognito
    import app.main as main

    try:
        app_config.settings.ENABLE_RATE_LIMITING = True

        importlib.reload(rate_limit)
        importlib.reload(auth_cognito)
        importlib.reload(main)

        app = main.app

        def override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = override_get_db

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
            lambda token: {"sub": "rluser", "email": "rl@example.com", "name": "Rate Limited User"},
        )

        with TestClient(app) as client:
            statuses: list[int] = []
            for _ in range(11):
                resp = client.post(
                    "/auth/cognito/login",
                    json={"email": "rl@example.com", "password": "Password12345!"},
                )
                statuses.append(resp.status_code)

            assert statuses[:10] == [200] * 10, statuses
            assert statuses[10] == 429, statuses
            detail = resp.json()
            assert detail["error"] == "RATE_LIMITED"
    finally:
        app_config.settings.ENABLE_RATE_LIMITING = False
        importlib.reload(rate_limit)
        importlib.reload(auth_cognito)
        importlib.reload(main)


