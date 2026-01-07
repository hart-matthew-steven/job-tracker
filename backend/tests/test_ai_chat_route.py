from __future__ import annotations

import pytest

from app.services.ai_usage import AIChatResult, AIUsageExceededReservationError
from app.services.credits import CreditsService
from app.services.openai_client import OpenAIClientError


class _FakeOrchestrator:
    def __init__(self, required_credits: int, result: AIChatResult | None, exc: Exception | None):
        self.required_credits = required_credits
        self._result = result
        self._exception = exc

    def estimate_reserved_credits(self, messages):
        return self.required_credits

    def run_chat(self, *, user, messages, request_id: str):
        if self._exception:
            raise self._exception
        return self._result


def _patch_orchestrator(monkeypatch, required_credits: int, result: AIChatResult | None = None, exc: Exception | None = None):
    def _factory(*args, **kwargs):
        return _FakeOrchestrator(required_credits, result, exc)

    monkeypatch.setattr("app.routes.ai_chat.AIUsageOrchestrator", _factory)


def _seed(db_session, user_id: int, cents: int):
    CreditsService(db_session).apply_ledger_entry(
        user_id,
        amount_cents=cents,
        source="admin",
        description="seed",
        idempotency_key=f"seed-{user_id}-{cents}",
    )


def test_ai_chat_success(client, db_session, users, monkeypatch):
    user, _ = users
    _seed(db_session, user.id, 20_000)
    result = AIChatResult(
        request_id="req-success",
        response_text="Hello!",
        model="gpt-4.1-mini",
        prompt_tokens=1_000,
        completion_tokens=500,
        total_tokens=1_500,
        credits_used_cents=250,
        credits_refunded_cents=50,
        credits_reserved_cents=300,
        balance_cents=19_750,
    )
    _patch_orchestrator(monkeypatch, required_credits=400, result=result)

    resp = client.post(
        "/ai/chat",
        json={
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Say hi"},
            ],
            "request_id": "req-success",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["response_text"] == "Hello!"
    assert body["credits_used_cents"] == 250
    assert body["credits_remaining_cents"] == 19_750


def test_ai_chat_insufficient_balance(client, users, monkeypatch):
    user, _ = users
    # Default balance is zero.
    _patch_orchestrator(monkeypatch, required_credits=1_000, result=None)

    resp = client.post(
        "/ai/chat",
        json={
            "messages": [{"role": "user", "content": "Need credits"}],
            "request_id": "req-low",
        },
    )
    assert resp.status_code == 402


@pytest.mark.parametrize(
    "exception,expected_status",
    [
        (OpenAIClientError("boom"), 502),
        (AIUsageExceededReservationError(reserved_cents=100, actual_cents=200, request_id="req"), 500),
    ],
)
def test_ai_chat_error_paths(client, db_session, users, monkeypatch, exception, expected_status):
    user, _ = users
    _seed(db_session, user.id, 5_000)
    result = AIChatResult(
        request_id="req-error",
        response_text="",
        model="gpt-4.1-mini",
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        credits_used_cents=0,
        credits_refunded_cents=0,
        credits_reserved_cents=0,
        balance_cents=5_000,
    )
    _patch_orchestrator(monkeypatch, required_credits=500, result=result, exc=exception)

    resp = client.post(
        "/ai/chat",
        json={
            "messages": [{"role": "user", "content": "Trigger error"}],
            "request_id": "req-error",
        },
    )
    assert resp.status_code == expected_status

