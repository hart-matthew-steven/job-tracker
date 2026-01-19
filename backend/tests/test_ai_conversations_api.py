from __future__ import annotations

from contextlib import contextmanager

from app.core import config as app_config
from app.main import app
from app.routes import ai_conversations as ai_routes
from app.routes.ai_conversations import (
    get_ai_concurrency_limiter,
)
from app.services import rate_limiter as rate_limiter_module
from app.services.credits import CreditsService, format_cents_to_dollars
from app.services.limits import InMemoryConcurrencyLimiter
from app.services.rate_limiter import RateLimitResult
from app.services.openai_client import OpenAIChatResponse, OpenAIUsage


def _seed_user_credits(db_session, user_id: int, amount: int = 50_000) -> None:
    service = CreditsService(db_session)
    service.apply_ledger_entry(
        user_id,
        amount_cents=amount,
        source="admin",
        idempotency_key=f"seed-{user_id}-{amount}",
        description="seed credits",
    )


class _FakeOpenAIClient:
    def __init__(self, response_text: str):
        usage = OpenAIUsage(prompt_tokens=1_000, completion_tokens=500, total_tokens=1_500)
        self._response = OpenAIChatResponse(
            request_id="req-static",
            response_id="resp-static",
            model=app_config.settings.OPENAI_MODEL,
            message=response_text,
            usage=usage,
        )

    def chat_completion(self, *, messages, request_id: str, max_tokens: int | None = None):
        return self._response


@contextmanager
def _stub_openai(monkeypatch, response_text: str):
    usage = OpenAIUsage(prompt_tokens=1_000, completion_tokens=500, total_tokens=1_500)
    fake_response = OpenAIChatResponse(
        request_id="req-static",
        response_id="resp-static",
        model=app_config.settings.OPENAI_MODEL,
        message=response_text,
        usage=usage,
    )

    def fake_chat(self, *, messages, request_id: str, max_tokens: int | None = None):
        return fake_response

    monkeypatch.setattr("app.services.openai_client.OpenAIClient.chat_completion", fake_chat)


@contextmanager
def override_concurrency_limit(concurrent_limit: int = 10):
    concurrency_limiter = InMemoryConcurrencyLimiter(concurrent_limit)
    original_concurrency = ai_routes._concurrency_limiter
    ai_routes._concurrency_limiter = concurrency_limiter
    with _override_dependency(get_ai_concurrency_limiter, lambda: concurrency_limiter):
        yield concurrency_limiter
    ai_routes._concurrency_limiter = original_concurrency


class _CountingLimiter:
    def __init__(self, allowed_requests: int, retry_after: int = 5) -> None:
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


def test_create_conversation_without_message(client, db_session, users, monkeypatch):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    _stub_openai(monkeypatch, response_text="no message")
    with override_concurrency_limit():
        resp = client.post("/ai/conversations", json={"title": "My Chat"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "My Chat"
    assert body["messages"] == []
    assert body["latest_summary"] is None
    ctx = body["context_status"]
    assert ctx["token_budget"] == app_config.settings.AI_CONTEXT_TOKEN_BUDGET
    assert ctx["tokens_used"] >= 0


def test_create_conversation_with_initial_message(client, db_session, users, monkeypatch):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    _stub_openai(monkeypatch, response_text="Assist reply")
    with override_concurrency_limit():
        resp = client.post(
            "/ai/conversations",
            json={"title": "Resume Chat", "message": "Please review my resume."},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"
    assert data["messages"][1]["content_text"] == "Assist reply"
    assert data["context_status"]["token_budget"] == app_config.settings.AI_CONTEXT_TOKEN_BUDGET


def test_post_message_appends_and_returns_balance(client, db_session, users, monkeypatch):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    _stub_openai(monkeypatch, response_text="Second reply")
    with override_concurrency_limit():
        create = client.post("/ai/conversations", json={"message": "start"})
        conv_id = create.json()["id"]

        resp = client.post(
            f"/ai/conversations/{conv_id}/messages",
            json={"content": "What should I improve?"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["assistant_message"]["content_text"] == "Second reply"
    assert body["credits_remaining_dollars"] == format_cents_to_dollars(body["credits_remaining_cents"])
    assert body["assistant_message"]["balance_remaining_cents"] == body["credits_remaining_cents"]


def test_rate_limit_enforced(client, db_session, users, monkeypatch):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    _stub_openai(monkeypatch, response_text="ok")

    create = client.post("/ai/conversations", json={"title": "Limiter"})
    conversation_id = create.json()["id"]

    limiter = _CountingLimiter(allowed_requests=1, retry_after=4)
    previous_enabled = app_config.settings.RATE_LIMIT_ENABLED
    rate_limiter_module._limiter = limiter  # type: ignore[attr-defined]
    app_config.settings.RATE_LIMIT_ENABLED = True
    try:
        with override_concurrency_limit():
            resp1 = client.post(
                f"/ai/conversations/{conversation_id}/messages",
                json={"content": "first"},
            )
            assert resp1.status_code == 201
            assert limiter.calls == 1

            resp2 = client.post(
                f"/ai/conversations/{conversation_id}/messages",
                json={"content": "second"},
            )
            assert resp2.status_code == 429
            assert resp2.headers.get("Retry-After") == "4"
    finally:
        app_config.settings.RATE_LIMIT_ENABLED = previous_enabled
        rate_limiter_module.reset_rate_limiter()


def test_message_insufficient_credits_shape(client, users):
    user, _ = users
    # user has zero credits by default
    create = client.post("/ai/conversations", json={"title": "No credits"})
    assert create.status_code == 201
    conversation_id = create.json()["id"]

    resp = client.post(
        f"/ai/conversations/{conversation_id}/messages",
        json={"content": "Need help with a cover letter."},
    )

    assert resp.status_code == 402
    body = resp.json()
    assert body.get("message") == "Insufficient credits."
    assert body.get("error") == "HTTP_ERROR"


def test_summaries_generated_and_context_meter(client, db_session, users, monkeypatch):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    original_message_threshold = app_config.settings.AI_SUMMARY_MESSAGE_THRESHOLD
    original_token_threshold = app_config.settings.AI_SUMMARY_TOKEN_THRESHOLD
    original_chunk_size = app_config.settings.AI_SUMMARY_CHUNK_SIZE
    original_budget = app_config.settings.AI_CONTEXT_TOKEN_BUDGET
    app_config.settings.AI_SUMMARY_MESSAGE_THRESHOLD = 2
    app_config.settings.AI_SUMMARY_TOKEN_THRESHOLD = 0
    app_config.settings.AI_SUMMARY_CHUNK_SIZE = 2
    app_config.settings.AI_CONTEXT_TOKEN_BUDGET = 100
    summary_calls = {"count": 0}

    def fake_summary(self, *, previous_summary, new_messages):
        summary_calls["count"] += 1
        return "Summary chunk", OpenAIUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    monkeypatch.setattr("app.services.ai_conversation.ConversationSummarizer.summarize", fake_summary)

    captured_payloads = []
    fake_response = OpenAIChatResponse(
        request_id="req-static",
        response_id="resp-static",
        model=app_config.settings.OPENAI_MODEL,
        message="OK",
        usage=OpenAIUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
    )

    def fake_chat(self, *, messages, request_id: str, max_tokens: int | None = None):
        captured_payloads.append(messages)
        return fake_response

    monkeypatch.setattr("app.services.openai_client.OpenAIClient.chat_completion", fake_chat)

    try:
        with override_concurrency_limit():
            create = client.post("/ai/conversations", json={"message": "hello"})
            conversation_id = create.json()["id"]
            client.post(f"/ai/conversations/{conversation_id}/messages", json={"content": "second"})
            # send third message to ensure summary is used in context
            client.post(f"/ai/conversations/{conversation_id}/messages", json={"content": "third"})
    finally:
        app_config.settings.AI_SUMMARY_MESSAGE_THRESHOLD = original_message_threshold
        app_config.settings.AI_SUMMARY_TOKEN_THRESHOLD = original_token_threshold
        app_config.settings.AI_SUMMARY_CHUNK_SIZE = original_chunk_size
        app_config.settings.AI_CONTEXT_TOKEN_BUDGET = original_budget

    assert summary_calls["count"] >= 1
    detail = client.get(f"/ai/conversations/{conversation_id}").json()
    assert detail["latest_summary"]["summary_text"] == "Summary chunk"
    assert detail["context_status"]["last_summarized_at"] is not None
    # Ensure summary message is injected into the latest OpenAI payload
    last_call_messages = captured_payloads[-1]
    assert any(
        msg["role"] == "system" and "Conversation summary" in msg["content"]
        for msg in last_call_messages
    )


def test_delete_conversation_removes_history(client, db_session, users):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    create = client.post("/ai/conversations", json={"title": "To delete"})
    assert create.status_code == 201
    conversation_id = create.json()["id"]

    delete = client.delete(f"/ai/conversations/{conversation_id}")
    assert delete.status_code == 204

    # Ensure it is gone
    get_resp = client.get(f"/ai/conversations/{conversation_id}")
    assert get_resp.status_code == 404


def test_rename_conversation(client, db_session, users):
    user, _ = users
    _seed_user_credits(db_session, user.id)

    create = client.post("/ai/conversations", json={"title": "Old"})
    conversation_id = create.json()["id"]

    resp = client.patch(f"/ai/conversations/{conversation_id}", json={"title": "Renamed"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Renamed"

    resp = client.patch(f"/ai/conversations/{conversation_id}", json={"title": "  "})
    assert resp.status_code == 200
    assert resp.json()["title"] is None


@contextmanager
def _override_dependency(dep, func):
    prev = app.dependency_overrides.get(dep)
    app.dependency_overrides[dep] = func
    try:
        yield
    finally:
        if prev is None:
            app.dependency_overrides.pop(dep, None)
        else:
            app.dependency_overrides[dep] = prev

