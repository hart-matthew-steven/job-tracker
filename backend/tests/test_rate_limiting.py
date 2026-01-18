from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from app.services import rate_limiter as rate_limiter_module
from app.services.ai_usage import AIChatResult
from app.services.rate_limiter import RateLimitResult


class _CountingLimiter:
    def __init__(self, allowed_requests: int, retry_after: int = 5):
        self.allowed_requests = allowed_requests
        self.retry_after = retry_after
        self.calls = 0

    def check(self, *, identifier: str, route_key: str, limit: int, window_seconds: int, now: int | None = None):
        self.calls += 1
        allowed = self.calls <= self.allowed_requests
        remaining = max(0, limit - self.calls)
        retry = self.retry_after if not allowed else 0
        now_ts = int(now or 0)
        window_start = now_ts - (now_ts % window_seconds) if window_seconds else now_ts
        reset_epoch = window_start + (window_seconds or 0)
        limiter_key = f"route:{route_key}:window:{window_seconds}"
        return RateLimitResult(
            allowed=allowed,
            retry_after_seconds=retry,
            limit=limit,
            remaining=remaining,
            count=self.calls,
            window_reset_epoch=reset_epoch,
            limiter_key=limiter_key,
            window_seconds=window_seconds,
        )


@pytest.mark.usefixtures("_stub_s3")
def test_ai_chat_rate_limit_returns_429(monkeypatch, client: TestClient):
    """
    Ensure the custom Dynamo-backed rate limiter enforces HTTP 429 responses on AI routes.
    """

    limiter = _CountingLimiter(allowed_requests=2, retry_after=7)
    rate_limiter_module._limiter = limiter  # type: ignore[attr-defined]

    fake_result = AIChatResult(
        usage_id=1,
        request_id="req",
        response_id="resp",
        response_text="ok",
        model="gpt",
        prompt_tokens=10,
        completion_tokens=5,
        total_tokens=15,
        credits_used_cents=10,
        credits_refunded_cents=0,
        credits_reserved_cents=10,
        balance_cents=100,
    )

    monkeypatch.setattr("app.routes.ai_chat.AIUsageOrchestrator.run_chat", lambda *args, **kwargs: fake_result)
    monkeypatch.setattr("app.routes.ai_chat.AIUsageOrchestrator.estimate_reserved_credits", lambda *args, **kwargs: 1)
    monkeypatch.setattr("app.services.credits.CreditsService.get_balance_cents", lambda self, user_id: 10_000)

    payload = {
        "request_id": "rate-test",
        "messages": [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Say hi."},
        ],
    }

    first = client.post("/ai/chat", json=payload)
    second = client.post("/ai/chat", json=payload)
    third = client.post("/ai/chat", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.headers.get("Retry-After") == "7"
    body = third.json()
    assert body["error"] == "RATE_LIMITED"
    assert body["details"]["retry_after_seconds"] == 7
