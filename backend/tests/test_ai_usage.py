from __future__ import annotations

from app.core import config as app_config
from app.models.credit import AIUsage
from app.services.ai_usage import (
    AIPricing,
    AIUsageOrchestrator,
)
from app.services.credits import CreditsService, InsufficientCreditsError
from app.services.openai_client import OpenAIChatResponse, OpenAIUsage


def _make_response(request_id: str, *, prompt_tokens: int, completion_tokens: int, text: str = "ok"):
    usage = OpenAIUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
    )
    return OpenAIChatResponse(
        request_id=request_id,
        response_id=f"resp-{request_id}",
        model=app_config.settings.OPENAI_MODEL,
        message=text,
        usage=usage,
    )


class _FakeOpenAIClient:
    def __init__(self, responses: list[OpenAIChatResponse]):
        self._responses = responses
        self.calls = 0

    def chat_completion(self, *, messages, request_id: str, max_tokens: int | None = None):
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


def _seed_credits(db_session, user_id: int, amount: int = 50_000):
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user_id,
        amount_cents=amount,
        source="admin",
        idempotency_key=f"seed-{user_id}-{amount}",
        description="seed credits",
    )


def test_orchestrator_reserves_and_finalizes(db_session, users):
    user, _ = users
    _seed_credits(db_session, user.id)

    fake_client = _FakeOpenAIClient(
        [
            _make_response(
                "req-1",
                prompt_tokens=20_000,
                completion_tokens=5_000,
                text="hello world",
            )
        ]
    )
    estimator = lambda messages: (18_000, 4_000)
    orchestrator = AIUsageOrchestrator(
        db_session,
        openai_client=fake_client,
        token_estimator=estimator,
    )

    result = orchestrator.run_chat(
        user=user,
        messages=[{"role": "user", "content": "Hello there"}],
        request_id="req-1",
    )
    pricing = AIPricing()
    estimated_cost = pricing.cost_from_tokens(
        model=app_config.settings.OPENAI_MODEL,
        prompt_tokens=18_000,
        completion_tokens=4_000,
    )
    expected_reserved = pricing.apply_buffer(max(estimated_cost, 1), app_config.settings.AI_CREDITS_RESERVE_BUFFER_PCT)
    actual_cost = pricing.cost_from_tokens(
        model=app_config.settings.OPENAI_MODEL,
        prompt_tokens=20_000,
        completion_tokens=5_000,
    )

    assert result.usage_id is not None
    assert result.credits_reserved_cents == expected_reserved
    assert result.credits_used_cents == actual_cost
    assert result.credits_refunded_cents == expected_reserved - actual_cost
    assert fake_client.calls == 1

    usage_row = (
        db_session.query(AIUsage)
        .filter(AIUsage.user_id == user.id, AIUsage.request_id == "req-1")
        .one()
    )
    assert usage_row.status == "succeeded"
    assert usage_row.response_text == "hello world"


def test_orchestrator_idempotent_on_success(db_session, users):
    user, _ = users
    _seed_credits(db_session, user.id)

    fake_client = _FakeOpenAIClient(
        [
            _make_response("req-2", prompt_tokens=10_000, completion_tokens=3_000, text="first"),
        ]
    )
    orchestrator = AIUsageOrchestrator(
        db_session,
        openai_client=fake_client,
        token_estimator=lambda messages: (12_000, 3_000),
    )

    first = orchestrator.run_chat(
        user=user,
        messages=[{"role": "user", "content": "Explain idempotency"}],
        request_id="req-2",
    )
    second = orchestrator.run_chat(
        user=user,
        messages=[{"role": "user", "content": "Explain idempotency"}],
        request_id="req-2",
    )

    assert first.response_text == second.response_text == "first"
    assert fake_client.calls == 1


def test_orchestrator_handles_large_actual_cost(db_session, users):
    user, _ = users
    _seed_credits(db_session, user.id, amount=200_000)

    fake_client = _FakeOpenAIClient(
        [
            _make_response("req-3", prompt_tokens=5_000_000, completion_tokens=2_000_000, text="too big"),
        ]
    )
    orchestrator = AIUsageOrchestrator(
        db_session,
        openai_client=fake_client,
        token_estimator=lambda messages: (10_000, 2_000),
    )

    result = orchestrator.run_chat(
        user=user,
        messages=[{"role": "user", "content": "large response please"}],
        request_id="req-3",
    )
    assert result.credits_refunded_cents == 0
    assert result.credits_used_cents >= result.credits_reserved_cents


def test_default_estimator_uses_tokenizer(db_session):
    fake_client = _FakeOpenAIClient([_make_response("req-default", prompt_tokens=1_000, completion_tokens=200)])
    orchestrator = AIUsageOrchestrator(db_session, openai_client=fake_client)
    messages = [
        {"role": "system", "content": "You are concise."},
        {"role": "user", "content": "Summarize the attached resume."},
    ]
    reserved = orchestrator.estimate_reserved_credits(messages)
    prompt_tokens, completion_tokens = orchestrator._default_token_estimator(messages)
    base = orchestrator.pricing.cost_from_tokens(
        model=app_config.settings.OPENAI_MODEL,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    expected_reserved = orchestrator.pricing.apply_buffer(max(base, 1), app_config.settings.AI_CREDITS_RESERVE_BUFFER_PCT)
    assert reserved == expected_reserved


def test_pricing_cost_from_tokens():
    pricing = AIPricing()
    cost = pricing.cost_from_tokens(model="gpt-4.1-mini", prompt_tokens=1_000_000, completion_tokens=0)
    assert cost == 15  # $0.15 * 100 credits


def test_orchestrator_charges_delta_when_balance_allows(db_session, users):
    user, _ = users
    _seed_credits(db_session, user.id, amount=100_000)

    fake_client = _FakeOpenAIClient(
        [
            _make_response("req-4", prompt_tokens=50_000, completion_tokens=20_000, text="delta ok"),
        ]
    )
    orchestrator = AIUsageOrchestrator(
        db_session,
        openai_client=fake_client,
        token_estimator=lambda messages: (10_000, 2_000),
    )

    result = orchestrator.run_chat(
        user=user,
        messages=[{"role": "user", "content": "Need long answer"}],
        request_id="req-4",
    )
    assert result.credits_refunded_cents >= 0
    assert fake_client.calls == 1


def test_orchestrator_delta_fails_without_balance(db_session, users):
    user, _ = users
    _seed_credits(db_session, user.id, amount=200)

    fake_client = _FakeOpenAIClient(
        [
            _make_response("req-5", prompt_tokens=10_000_000, completion_tokens=5_000_000, text="large"),
        ]
    )
    orchestrator = AIUsageOrchestrator(
        db_session,
        openai_client=fake_client,
        token_estimator=lambda messages: (1_000, 500),
    )

    try:
        orchestrator.run_chat(
            user=user,
            messages=[{"role": "user", "content": "huge output"}],
            request_id="req-5",
        )
    except InsufficientCreditsError:
        pass
    else:  # pragma: no cover
        raise AssertionError("Expected InsufficientCreditsError")

