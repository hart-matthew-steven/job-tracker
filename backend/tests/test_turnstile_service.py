from __future__ import annotations

import httpx
import pytest

from app.services import turnstile
from app.services.turnstile import (
    TurnstileConfigurationError,
    TurnstileVerificationError,
    verify_turnstile_token,
)


class _DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_verify_turnstile_token_success(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr(turnstile.httpx, "post", lambda *a, **k: _DummyResponse({"success": True}))

    # Should not raise
    verify_turnstile_token("token-123", remote_ip="1.1.1.1")


def test_verify_turnstile_token_failure(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "secret")
    monkeypatch.setattr(turnstile.httpx, "post", lambda *a, **k: _DummyResponse({"success": False}))

    with pytest.raises(TurnstileVerificationError):
        verify_turnstile_token("bad-token")


def test_verify_turnstile_token_network_error(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "secret")

    def _raise(*args, **kwargs):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(turnstile.httpx, "post", _raise)

    with pytest.raises(TurnstileVerificationError):
        verify_turnstile_token("token")


def test_verify_turnstile_token_configuration_missing(monkeypatch):
    monkeypatch.setattr(turnstile.settings, "TURNSTILE_SECRET_KEY", "")

    with pytest.raises(TurnstileConfigurationError):
        verify_turnstile_token("token")


