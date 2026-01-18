from __future__ import annotations

import json
import logging

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
import pytest

from app.dependencies import rate_limit as rate_limit_dependency
from app.services.rate_limiter import RateLimitResult


class _StubLimiter:
    def __init__(self, allow_until: int):
        self.allow_until = allow_until
        self.calls = 0

    def check(self, *, identifier: str, route_key: str, limit: int, window_seconds: int, now: int | None = None):
        self.calls += 1
        allowed = self.calls <= self.allow_until
        remaining = max(0, limit - self.calls)
        limiter_key = f"route:{route_key}:window:{window_seconds}"
        now_ts = int(now or 0)
        window_start = now_ts - (now_ts % window_seconds) if window_seconds else now_ts
        reset_epoch = window_start + (window_seconds or 0)
        return RateLimitResult(
            allowed=allowed,
            retry_after_seconds=0 if allowed else 5,
            limit=limit,
            remaining=remaining,
            count=self.calls,
            window_reset_epoch=reset_epoch,
            limiter_key=limiter_key,
            window_seconds=window_seconds,
        )


@pytest.fixture()
def limited_app(monkeypatch):
    limiter = _StubLimiter(allow_until=2)
    monkeypatch.setattr(rate_limit_dependency, "get_rate_limiter", lambda: limiter)

    app = FastAPI()

    @app.middleware("http")
    async def attach_user(request, call_next):  # noqa: D401
        class _User:
            id = 123

        request.state.user = _User()
        return await call_next(request)

    dependency = rate_limit_dependency.require_rate_limit("test_route", limit=2, window_seconds=60)

    @app.get("/limited", dependencies=[Depends(dependency)])
    def _limited():
        return {"ok": True}

    return TestClient(app)


def test_rate_limit_logs_allow_and_block(caplog, limited_app: TestClient):
    caplog.set_level(logging.INFO, logger="app.dependencies.rate_limit")

    first = limited_app.get("/limited")
    second = limited_app.get("/limited")
    third = limited_app.get("/limited")

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429

    records = [
        json.loads(record.message)
        for record in caplog.records
        if record.name == "app.dependencies.rate_limit"
    ]
    assert len(records) == 3

    assert records[0]["decision"] == "allow"
    assert records[0]["user_id"] == 123
    assert records[2]["decision"] == "block"
    assert records[2]["limiter_key"] == "route:test_route:window:60"
    assert records[2]["remaining"] == 0
    assert records[2]["reset_epoch"] >= records[2]["window_seconds"]
