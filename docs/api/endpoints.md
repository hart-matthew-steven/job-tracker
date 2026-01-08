# API Endpoints

This is the endpoint inventory for the backend API.

Guidelines:
- Keep entries short and consistent.
- Include request/response examples only for stable endpoints.
- Prefer linking to schemas/types in code rather than duplicating large payloads.

---

## Health / Meta

- `GET /health`
  - Purpose: health check
  - Auth: none
  - Response: `{ "status": "ok" }` (example)

---

## Rate limiting

- All `/ai/*`, `/auth/cognito/*`, and `/jobs/{id}/documents/presign-upload` endpoints are protected by a DynamoDB-backed fixed-window limiter. The table (`jobapptracker-rate-limits`) uses `pk=user:{user_id}` or `ip:{client_ip}` and `sk=route:{route_key}:window:{seconds}` to track counters with TTL (`expires_at`).
- When the limiter fires, the API returns HTTP 429 with `{"error":"RATE_LIMITED","details":{"retry_after_seconds":N}}` and a `Retry-After` header. Tuning knobs live in `.env` (`RATE_LIMIT_ENABLED`, `RATE_LIMIT_DEFAULT_*`, `AI_RATE_LIMIT_*`).

---

## Admin / Operational

> All admin endpoints require Cognito auth **and** `users.is_admin=true`. The reusable dependency `require_admin_user` enforces both.

- `GET /admin/rate-limits/status?user_id=123`
  - Auth: Bearer (admin only)
  - Response: `{ "user_id": 123, "records": [{ "limiter_key": "route:ai_chat:window:60", "window_seconds": 60, "limit": 10, "count": 3, "remaining": 7, "expires_at": 1704752852, "record_type": "counter" }] }`
  - Notes: Queries the DynamoDB limiter table for the given user (or IP if you substitute `user_id` with an internal IP-only identifier) and returns all active windows + overrides. Expired rows are filtered server-side so the UI only shows actionable data.

- `POST /admin/rate-limits/reset`
  - Auth: Bearer (admin only)
  - Body: `{ "user_id": 123 }`
  - Response: `{ "user_id": 123, "deleted": 4 }`
  - Notes: Batch-deletes every limiter record (including overrides) for the user so the next request starts fresh. Safe to call multiple times; no rows are removed if the table has already expired naturally.

- `POST /admin/rate-limits/override`
  - Auth: Bearer (admin only)
  - Body: `{ "user_id": 123, "limit": 50, "window_seconds": 60, "ttl_seconds": 900 }`
  - Response: `{ "user_id": 123, "limit": 50, "window_seconds": 60, "expires_at": 1704753000 }`
  - Notes: Writes `sk=override:global` with the provided limit/window and a required TTL. The limiter checks this record before incrementing route keys, so overrides apply to all protected endpoints for that user until the TTL expires or the admin calls `/reset`.

---

## Auth (`/auth/cognito/*`)

- `POST /auth/cognito/signup`
  - Auth: none
  - Body: `{ email, password, name, turnstile_token }`
  - Notes: backend verifies Cloudflare Turnstile token before calling Cognito `SignUp`

- `POST /auth/cognito/confirm`
  - Auth: none
  - Body: `{ email, code }`

- `POST /auth/cognito/login`
  - Auth: none
  - Body: `{ email, password }`
  - Notes: returns `{status:"OK",tokens:{...}}` on success or `{status:"CHALLENGE",next_step,session}` when Cognito requires MFA/setup

- `POST /auth/cognito/challenge`
  - Auth: none
  - Body: `{ email, challenge_name, session, responses }`
  - Notes: wraps Cognito `RespondToAuthChallenge` (e.g., SOFTWARE_TOKEN_MFA)

- `POST /auth/cognito/mfa/setup`
  - Auth: none
  - Body: `{ session, label? }`
  - Notes: calls Cognito `AssociateSoftwareToken`, returns `{secret_code, otpauth_uri, session}`

- `POST /auth/cognito/mfa/verify`
  - Auth: none
  - Body: `{ email, session, code, friendly_name? }`
  - Notes: calls `VerifySoftwareToken`, then `RespondToAuthChallenge` with `ANSWER=SUCCESS`

- `POST /auth/cognito/refresh`
  - Auth: none
  - Body: `{ refresh_token }`
  - Notes: proxies Cognito `REFRESH_TOKEN_AUTH`, returns updated tokens

- `POST /auth/cognito/verification/send`
  - Auth: none (rate-limited; responds generically)
  - Body: `{ email }`
  - Notes: generates a 6-digit code, stores a salted hash, enforces TTL/cooldown, and emails the code via Resend.

- `POST /auth/cognito/verification/confirm`
  - Auth: none
  - Body: `{ email, code }`
  - Notes: validates code hash/TTL/attempts, sets `users.is_email_verified=true`, syncs `email_verified=true` back to Cognito (`Username=cognito_sub`).

- `POST /auth/cognito/logout`
  - Auth: Bearer (optional)
  - Notes: best-effort API parity—clears SPA session; no server-side refresh store exists

---

## Users

- `GET /users/me`
  - Auth: Bearer
  - Response: includes `ui_preferences` JSON for persisted UI state (collapsed cards, etc.)

- `POST /users/me/change-password`
  - Auth: Bearer
  - Notes: revokes refresh tokens on success

- `GET /users/me/settings`
  - Auth: Bearer

- `PUT /users/me/settings`
  - Auth: Bearer
  - Body: `{ "auto_refresh_seconds": 0|10|30|60 }`

- `PATCH /users/me/ui-preferences`
  - Auth: Bearer
  - Body: `{ "preferences": { "job_details_notes_collapsed": true } }`
  - Notes: persists SPA/UI toggles (e.g., collapsed panels) across devices.

---

## Billing / Credits

- `GET /billing/credits/balance`
  - Auth: Bearer
  - Response: `{ "currency": "usd", "balance_cents": 5500, "balance_dollars": "55.00", "lifetime_granted_cents": 7000, "lifetime_spent_cents": 1500, "as_of": "2026-01-06T12:34:56Z" }`
  - Notes: All values come from live `credit_ledger` sums on every request—there is no cached balance.
  - Future AI endpoints will call `require_credits(...)` before executing and will return HTTP `402 PAYMENT_REQUIRED` if the user lacks sufficient credits.

- `GET /billing/credits/ledger?limit=50&offset=0`
  - Auth: Bearer
  - Response: `[{ "amount_cents": 2000, "source": "promo", "description": "...", "source_ref": "promo-jan", "created_at": "..." }, ... ]`
  - Notes: Entries are returned newest-first and leverage `(user_id, source_ref)` idempotency; Stripe/OpenAI integrations will add to this feed later.

- `GET /billing/me`
  - Auth: Bearer
  - Response: `{ "balance_cents": 5500, "stripe_customer_id": "cus_123", "ledger": [ ... ] }`
  - Notes: Returns a lightweight overview combining the current balance, linked Stripe customer id (if any), and the 10 most recent ledger entries including pack metadata.

- `GET /billing/packs`
  - Auth: none (public)
  - Response: `[{ "key": "starter", "credits": 500, "price_id": "price_123", "display_price_dollars": "5.00" }, ...]`
  - Notes: Packs are derived from `STRIPE_PRICE_MAP` (format: `pack_key:price_id:credits`). The frontend only sends the `pack_key`; the backend resolves price/credits.

- `POST /billing/stripe/checkout`
  - Auth: Bearer
  - Body: `{ "pack_key": "starter" }`
  - Response: `{ "checkout_session_id": "cs_test_123", "checkout_url": "https://checkout.stripe.com/...", "currency": "usd", "pack_key": "starter", "credits_granted": 500 }`
  - Notes: Pack information (Stripe price id + credits) is resolved server-side from `STRIPE_PRICE_MAP`. Checkout metadata includes `user_id`, `pack_key`, `credits_to_grant`, and `environment` so the webhook can mint credits deterministically. No balance changes occur until the webhook confirms a paid session.

- `POST /billing/stripe/webhook`
  - Auth: Stripe signature header (`Stripe-Signature`)
  - Body: Raw Stripe event JSON
  - Notes: Validates the signature, inserts/locks a `stripe_events` row, and uses metadata (`user_id`, `pack_key`, `credits_to_grant`) on `checkout.session.completed` events to mint a single ledger entry. Duplicate events short-circuit once the `stripe_event_id` is recorded. Failures mark `stripe_events.status=failed` and return HTTP 500 so Stripe retries.

- `POST /billing/credits/debug/spend`
  - Auth: Bearer (only available when `ENABLE_BILLING_DEBUG_ENDPOINT=true` and `ENV!=prod`)
  - Body: `{ "amount_cents": 250, "reason": "dev smoke test", "idempotency_key": "debug-1" }`
  - Notes: Dev-only helper to simulate credit consumption without going through the paid AI flow. Uses the same `spend_credits/require_credits` path the future OpenAI integration will call.

---

## AI usage

- `POST /ai/chat`
  - Auth: Bearer
  - Body:
    ```json
    {
      "request_id": "chat-123",
      "messages": [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Draft a follow-up email."}
      ]
    }
    ```
  - Response: `{ "request_id": "chat-123", "model": "gpt-4.1-mini", "response_text": "...", "prompt_tokens": 900, "completion_tokens": 350, "credits_used_cents": 240, "credits_refunded_cents": 60, "credits_reserved_cents": 300, "credits_remaining_cents": 4700, "credits_remaining_dollars": "47.00" }`
  - Notes: The backend tokenizes prompts with OpenAI’s tokenizer (`tiktoken`), budgets `AI_COMPLETION_TOKENS_MAX` completion tokens, applies `AI_CREDITS_RESERVE_BUFFER_PCT` (currently 25%), reserves *more* credits than needed, calls OpenAI, then finalizes the reservation with the actual cost. If the OpenAI response exceeds the reservation the entire reservation is refunded and the API returns HTTP 500 so the client can retry with a fresh request id. Passing the same `request_id` makes the call idempotent—success responses are replayed without hitting OpenAI again. Exceeding `AI_RATE_LIMIT_MAX_REQUESTS` within `AI_RATE_LIMIT_WINDOW_SECONDS` returns HTTP 429 with a `Retry-After` header.

### Conversations (`/ai/conversations*`)

- `POST /ai/conversations`
  - Auth: Bearer
  - Body: `{ "title": "Resume polish", "message": "Review my resume summary" }` (message optional)
  - Response: `ConversationDetailResponse` with the first page of messages.
  - Notes: Creates a durable conversation row. If `message` is provided the backend sends it to OpenAI, stores both the user + assistant messages, and returns the new thread. DynamoDB rate limiting + in-process concurrency limits are enforced whenever a message is sent (HTTP 429 on overage).

- `GET /ai/conversations?limit=20&offset=0`
  - Auth: Bearer
  - Response: `{ conversations: [{ id, title, message_count, created_at, updated_at }], next_offset }`
  - Notes: Lists the caller’s conversations ordered by `updated_at desc`. Subject to the same rate limiter as other AI routes.

- `GET /ai/conversations/{conversation_id}?limit=50&offset=0`
  - Auth: Bearer
  - Response: `ConversationDetailResponse` including paged messages (oldest-first).
  - Notes: Rejects access to conversations owned by another user.

- `POST /ai/conversations/{conversation_id}/messages`
  - Auth: Bearer
  - Body: `{ "content": "Draft a thank-you email" , "request_id": "msg-123" }`
  - Response: `{ conversation_id, user_message, assistant_message, credits_used_cents, credits_reserved_cents, credits_remaining_* }`
  - Notes: Appends a user message, builds a trimmed history (max `AI_MAX_CONTEXT_MESSAGES`), reserves credits, calls OpenAI, stores the assistant reply, and debits the final cost. Each `request_id` is idempotent. Returns 402 when the user lacks credits, 429 when the per-minute/concurrency guardrails fire, and 503 when OpenAI is temporarily unavailable.

---

## AI demo / reservation stub

- `POST /ai/demo`
  - Auth: Bearer
  - Body:
    ```
    {
      "idempotency_key": "demo-123",
      "estimated_cost_credits": 1200,
      "simulate_outcome": "success" | "fail",
      "actual_cost_credits": 900   # optional override when simulate_outcome=success
    }
    ```
  - Response: `{ reservation_id, correlation_id, status: "success"|"refunded", balance_cents, ledger_entries: [...] }`
  - Notes: Reserves credits (`entry_type=ai_reserve`), then either releases + charges (`ai_release` + `ai_charge`) or refunds (`ai_refund`). This endpoint is a smoke test for the reservation/finalize/refund primitives that real AI routes will call before contacting OpenAI.

---

## Jobs

- `GET /jobs`
  - Auth: Bearer
  - Notes: Supports `q`, `status[]`, `tag[]`, `tag_q` filters.

- `POST /jobs`
  - Auth: Bearer
  - Body: `JobApplicationCreate`
  - Notes: Triggered by the global “Create job” button that now lives in the header on desktop and mobile; there is no separate mobile-only endpoint.

- `GET /jobs/{job_id}`
  - Auth: Bearer

- `GET /jobs/{job_id}/details`
  - Auth: Bearer
  - Query: `activity_limit` (default 20, 1–200)
  - Notes: Returns `{ job, notes, interviews, activity: { items, next_cursor } }` so the Jobs page can hydrate in one request. Use `next_cursor` to fetch additional activity via `/jobs/{job_id}/activity`.

- `PATCH /jobs/{job_id}`
  - Auth: Bearer
  - Body: `JobApplicationUpdate`
  - Notes: Tag/status changes log activity entries.

- `GET /jobs/board`
  - Auth: Bearer
  - Response: `{ statuses: string[], jobs: JobBoardCard[], meta }`
  - Notes: Returns board-ready cards with `priority`, `last_action_at`, `next_action_at`, `next_action_title`, and `needs_follow_up` hints.

- `GET /jobs/search?q=term`
  - Auth: Bearer
  - Query: `q` (min length 1), `limit` (default 20)
  - Notes: Searches company/title/location + notes. Returns a board-style payload for the command palette.

### Activity

- `GET /jobs/{job_id}/activity`
  - Auth: Bearer
  - Query:
    - `limit` (default 20, 1–200)
    - `cursor_id` (optional) — fetch entries older than the given activity id
  - Response: `{ items: JobActivity[], next_cursor: number | null }`. Continue requesting with `cursor_id = next_cursor` until it returns `null`.

### Notes

- `GET /jobs/{job_id}/notes`
  - Auth: Bearer

- `POST /jobs/{job_id}/notes`
  - Auth: Bearer

- `DELETE /jobs/{job_id}/notes/{note_id}`
  - Auth: Bearer

### Interviews

- `GET /jobs/{job_id}/interviews`
  - Auth: Bearer

- `POST /jobs/{job_id}/interviews`
  - Auth: Bearer
  - Body: `JobInterviewCreate`

- `PATCH /jobs/{job_id}/interviews/{interview_id}`
  - Auth: Bearer
  - Body: `JobInterviewUpdate`

- `DELETE /jobs/{job_id}/interviews/{interview_id}`
  - Auth: Bearer

### Documents

- `GET /jobs/{job_id}/documents`
  - Auth: Bearer

- `POST /jobs/{job_id}/documents/presign-upload`
  - Auth: Bearer

- `POST /jobs/{job_id}/documents/confirm-upload`
  - Auth: Bearer

- `GET /jobs/{job_id}/documents/{doc_id}/presign-download`
  - Auth: Bearer

- `DELETE /jobs/{job_id}/documents/{doc_id}`
  - Auth: Bearer

- `POST /jobs/{job_id}/documents/{document_id}/scan-result`
  - Auth: Shared secret (`X-Scan-Secret`)
  - Notes: GuardDuty → backend scan callback path.

### Metrics

- `GET /jobs/metrics/activity?range_days=7`
  - Auth: Bearer
  - Notes: Returns `{ range_days, total_events, per_type }` for the activity pulse widget.

## Saved Views

- `GET /saved-views`
  - Auth: Bearer

- `POST /saved-views`
  - Auth: Bearer
  - Body: `SavedViewCreate`

- `PATCH /saved-views/{view_id}`
  - Auth: Bearer
  - Body: `SavedViewUpdate`

- `DELETE /saved-views/{view_id}`
  - Auth: Bearer

## Internal (GuardDuty/Lambda)

- `GET /internal/documents/{doc_id}`
  - Auth: Shared secret header (`X-Doc-Scan-Secret` preferred)
  - Notes: Debug helper to inspect scan status when GuardDuty is enabled.

- `POST /internal/documents/{doc_id}/scan-result`
  - Auth: Shared secret header
  - Notes: Legacy callback path; GuardDuty forwarder now uses `/jobs/{job_id}/documents/{document_id}/scan-result`.

---

## Updating this document

Update this file when:
- routes are added/removed/renamed
- request/response shapes change materially
- auth requirements change for an endpoint