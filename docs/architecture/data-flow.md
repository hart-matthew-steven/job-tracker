# Data Flow

This document describes how data moves through the system. It is written to be implementation-flexible (you can swap specific AWS services later) while keeping workflow and security properties stable.

---

## Legend

    [FE]   Frontend (React + Vite)
    [API]  Backend API (Python)
    [AWS]  AWS-managed services (storage/queue/db)
    [GD]   AWS GuardDuty Malware Protection for S3
    [DB]   Persistence layer (DB)

---

## High-Level System View

    User
      |
      v
    [FE]  --->  [API]  --->  [DB]
                 |
                 +----> [AWS S3]
                           |
                           v
                         [GD] (GuardDuty scans object)
                           |
                           v
                      [EventBridge]
                           |
                           v
                     [Lambda forwarder]
                           |
                           v
                         [API] --> [DB] (status updates)

---

## 1) User loads the app

    User
      |
      v
    [FE] --(GET /session, GET /apps, etc)--> [API] --> [DB]
      |
      v
    Renders UI

Key properties:
- Backend is the source of truth.
- Frontend remains thin and presentation-focused.
- Marketing/demo routes (`/` and `/demo/board`) are purely client-side; `/demo/board` renders seeded data without touching the backend so prospects can explore the board before authenticating.

---

## 2) Create or update a job application

    [FE] --(POST/PUT /applications)--> [API] --> [DB]
     ^                                  |
     |                                  v
     +-----------(JSON response)--------+

Optional (future):
    [API] --> [AWS Queue/Event] --> worker --> [DB] (analytics/audit)

---

## 2.5) Load a job’s full detail view (bundled endpoint)

    [FE] --(GET /jobs/{job_id}/details?activity_limit=20)--> [API] --> [DB]
      ^                                                         |
      |                                                         +--> notes (ordered newest→oldest)
      |                                                         +--> interviews (user-scoped)
      |                                                         +--> job activity (limited slice)
      +----------------(single JSON payload with {job,notes,interviews,activity})---------------+

Why: JobsPage used to fire four sequential requests (`GET /jobs/{id}`, `/notes`, `/interviews`, `/activity`). The new endpoint returns the entire bundle in one round trip so the UI hydrates immediately and latency stays low even on high-RTT networks. The `activity_limit` query param defaults to 20 (min 1, max 200) so the frontend can request a smaller slice when needed.

---

## 3) Upload a document (resume, cover letter, etc.)

### States (implemented)

There are two related fields:
- DB `scan_status`: `PENDING` → `CLEAN` | `INFECTED` | `ERROR`
- UI `status` (legacy UI lifecycle): `pending` → `scanning` → `uploaded` | `infected` | `failed`

### Flow (S3 → GuardDuty → EventBridge → Lambda → Backend callback)

    User
      |
      v
    [FE] POST /jobs/{id}/documents/presign-upload  --------------------+
      |                                                                |
      |  (DB row created; scan_status=PENDING; status=pending)          |
      |                                                                |
      +--> PUT presigned S3 URL (<=5MB) --> [AWS S3] (untrusted object) |
                                                                   +---+
                                                                   |
    [FE] POST /jobs/{id}/documents/confirm-upload  -----------------+
      |   (status=scanning; still scan_status=PENDING)
      |
      v
    [AWS S3] object uploaded
      |
      v
    [GuardDuty Malware Protection for S3] scans object (no file download by us)
      |
      v
    [EventBridge] receives GuardDuty scan completion event
      |
      v
    [Lambda: guardduty_scan_forwarder]
      |
      | extracts document_id + job_id from S3 key
      | verdict source of truth: S3 object tag GuardDutyMalwareScanStatus
      | (if verdict not in event, Lambda calls S3 GetObjectTagging)
      | maps verdict -> CLEAN/INFECTED/ERROR
      |
      +--> NO_THREATS_FOUND -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
      |                         updates scan_status=CLEAN; status=uploaded
      |
      +--> THREATS_FOUND    -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
      |                         updates scan_status=INFECTED; status=infected
      |
      +--> ERROR/UNKNOWN    -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
                               updates scan_status=ERROR; status=failed
      |
      | (Legacy internal endpoint `/internal/documents/{document_id}/scan-result` remains for manual/debug callbacks)

Security properties:
- Files are treated as hostile until scan_status == CLEAN.
- Backend blocks downloads unless scan_status == CLEAN.
- GuardDuty handles scanning without us downloading or processing untrusted files.
- Infected files remain in S3 but are marked as INFECTED in DB (download blocked).

### Dev note (current)

- In production the Lambda calls the App Runner API directly (e.g., `https://api.jobapptracker.dev/jobs/.../scan-result`).
- For local testing you can still point the Lambda at an ngrok tunnel, but production traffic no longer relies on ngrok.

---

## 4) Background processing (async jobs)

General pattern:

    [API] --> [AWS Queue/Jobs] --> worker --> [DB]
                         |
                         v
                      retries + DLQ (optional)

Reliability properties:
- Jobs should be idempotent where possible.
- Failures tracked and retryable.
- Status written to DB in a consistent format.

---

## 5) Stripe credit purchase flow

Text diagram:

    Authenticated user
      |
      v
    [FE] POST /billing/stripe/checkout (pack_key)
      |
      v
    [API] StripeService.ensure_customer(user) ---> [Stripe Customer]
      |
      v
    Resolve pack_key -> price_id + credits via STRIPE_PRICE_MAP
      |
      v
    Stripe Checkout (hosted payment page with pack metadata)
      |
      v
    Stripe Webhook --> /billing/stripe/webhook (signed)
      |
      v
    StripeService.process_event(event_id)
      |
      +--> writes audit row to [DB] stripe_events (unique stripe_event_id, status=pending)
      |
      +--> when session.payment_status == paid:
              CreditsService.apply_ledger_entry(
                  source="stripe",
                  source_ref=stripe_event_id,
                  pack_key=metadata.pack_key,
                  stripe_checkout_session_id=session.id,
                  stripe_payment_intent_id=session.payment_intent,
              )
      |
      +--> stripe_events.status updated to processed|skipped
      |
      v
    credit_ledger (amount_cents == credits_to_grant) ---> available balance

Key behaviors:
- Credits are defined per pack (1 credit == 1 cent). `STRIPE_PRICE_MAP` holds `pack_key:price_id:credits`, so changing pack pricing is a config change rather than a code change.
- Only the webhook can mint credits. Even if the checkout endpoint is spammed or the frontend drops, no credits are issued until Stripe proves the payment succeeded via a signed webhook and we’ve locked the relevant `stripe_events` row.
- Idempotency lives in two layers:
- `stripe_events.stripe_event_id` is unique, so re-delivered events are recorded once and marked `skipped`.
- `credit_ledger` enforces `(user_id, idempotency_key)` uniqueness. Stripe deposits use `event_id-deposit`; future spends use their own `idempotency_key`. Even if a webhook or usage call retries, the ledger row is written at most once.
- Spending is also ledger-driven: `spend_credits(user_id, amount, reason, idempotency_key)` locks the user row, recomputes the current balance, and inserts a negative ledger row only when the user has enough credits. If the balance is insufficient, the call fails with HTTP 402 and no rows are written.
- Failures (missing metadata, DB errors, etc.) set `stripe_events.status=failed`, capture the error message, and return HTTP 500 so Stripe retries instead of silently losing the purchase.
- Future AI usage charges will consume the credits that were minted here and log mirrored facts into `ai_usage` so USD costs remain explainable.

### Credits reservation + OpenAI usage flow

1. `reserve_credits` locks the user row (`SELECT ... FOR UPDATE`), verifies the live ledger balance, and writes an `ai_reserve` row (`amount_cents` negative, `status=reserved`, `correlation_id=uuid4`). This immediately reduces the available balance so concurrent AI requests cannot overspend.
2. The API counts prompt tokens with OpenAI’s tokenizer (`tiktoken`) and budgets `AI_COMPLETION_TOKENS_MAX` completion tokens before applying the buffer (`AI_CREDITS_RESERVE_BUFFER_PCT`, 25 % today) so small spikes in usage never push the account negative.
3. If the downstream OpenAI call succeeds, `finalize_charge` writes an `ai_release` row (+reserved amount) followed by an `ai_charge` row (−actual amount). The original `ai_reserve` row is marked `finalized`, so additional finalize attempts simply return the already-posted ledger entries.
4. If the OpenAI request fails—or if actual usage exceeds the reservation—`refund_reservation` writes an `ai_refund` row (+reserved amount) and marks the reservation `refunded`. The API returns HTTP 500 so the client can retry with a new `request_id`.
5. Each step requires its own per-user `idempotency_key` (e.g., `chat-1::reserve`, `chat-1::finalize`). Retried HTTP requests reuse the same ledger entries, keeping the flow idempotent end-to-end.
6. `POST /ai/chat` is the production entrypoint: it estimates cost, over-reserves, calls OpenAI, then finalizes/refunds based on actual usage. `POST /ai/demo` remains as a dev-only helper wired to the same helpers.

### AI conversation (durable thread) flow

1. `POST /ai/conversations` optionally accepts an initial `message`. Conversations live in `ai_conversations` keyed by `user_id`. If a message is provided the backend immediately creates the user-side `ai_messages` row before calling OpenAI so retries never drop user input.
2. All message sends (`POST /ai/conversations/{id}/messages`) run through `AIConversationService`:
   - Enforce `AI_MAX_INPUT_CHARS` and normalize whitespace.
   - Load the last `AI_MAX_CONTEXT_MESSAGES` `ai_messages` rows for that conversation (oldest-first) and append the new user message to form the OpenAI payload.
   - Attach/propagate a correlation id (`X-Request-Id` header if supplied, otherwise `uuid4`).
3. Guardrails fire before OpenAI is invoked:
   - The DynamoDB rate limiter enforces per-user/per-route budgets (`AI_RATE_LIMIT_MAX_REQUESTS` / `AI_RATE_LIMIT_WINDOW_SECONDS`). Because the table lives outside App Runner, limits hold even if multiple instances are running. Exceeding the budget raises HTTP 429 (with `Retry-After`) before we burn prepaid credits.
   - `InMemoryConcurrencyLimiter` (`AI_MAX_CONCURRENT_REQUESTS`) still prevents overlapping OpenAI calls on the same instance. This guard lives in-process (cheap and instantaneous) and is fine being node-local because concurrency is inherently tied to the work queued on that specific container.
4. `AIUsageOrchestrator.run_chat(...)` now accepts the conversation id + correlation id:
   - Tokenizes with `tiktoken`, budgets `AI_COMPLETION_TOKENS_MAX` completion tokens, applies `AI_CREDITS_RESERVE_BUFFER_PCT`, and reserves credits (ledger `ai_reserve` row).
   - Calls OpenAI with jittered retries (up to `AI_OPENAI_MAX_RETRIES`). Each call passes the correlation id so upstream logs are traceable.
   - If actual cost ≤ reserved → finalize charge + refund the difference.
   - If actual cost > reserved → finalize the reserved amount, attempt to `spend_credits` for the delta (`idempotency_key="{request_id}::delta"`), and refund/return HTTP 402 when the user lacks funds.
   - Any OpenAI exception triggers `refund_reservation` and HTTP 503 so the client can retry.
5. Successful runs persist the assistant message (`ai_messages`), update `ai_usage` with `conversation_id`/`message_id`/`response_id`, bump `ai_conversations.updated_at`, and return `{ user_message, assistant_message, credits_used_cents, credits_remaining_* }`.
6. `GET /ai/conversations`/`GET /ai/conversations/{id}` page through `ai_conversations` + `ai_messages` (oldest-first). The frontend does not need to resend the entire transcript; it can resume from the last known message id.

### Rate limiting (DynamoDB)

1. For each protected route we call `require_rate_limit(route_key, limit, window_seconds)` before hitting business logic.
2. The dependency inspects `request.state.user`. If authenticated it builds `pk=user:{user_id}`, otherwise `pk=ip:{client_ip}`. The sort key is `route:{route_key}:window:{window_seconds}`.
3. `window_start = now - (now % window_seconds)` and `expires_at = window_start + window_seconds + ttl_buffer`.
4. `DynamoRateLimiter.check(...)` issues a single `UpdateItem`:
   - Condition: `attribute_not_exists(window_start) OR window_start = :window_start`
   - Update: `window_start = :window_start`, `count = if_not_exists(count, 0) + 1`, `expires_at = :expires_at`
   - On `ConditionalCheckFailedException` it resets the window with a second `UpdateItem` that sets `count = 1`.
5. If the returned `count` is above the configured limit we compute `retry_after = max(1, window_start + window_seconds - now)` and raise HTTP 429 with `Retry-After`.
6. DynamoDB’s TTL evicts items automatically, so App Runner can scale horizontally without sharing state through Redis/ElastiCache.

---

## Dev vs Prod Differences

### Development (ngrok)
Only ingress changes:

    Internet --> ngrok --> [API(local)] --> [DB(local or dev)]
                                   |
                                   v
                              [AWS(dev)] (optional)

Rules:
- Keep ngrok short-lived.
- Do not bypass scan flow for convenience.
- Do not leak tokens/URLs into logs or commits.

### Production (AWS)
Stable ingress + hardened controls:

    Internet --> [AWS Ingress] --> [API] --> [DB]
                          |
                          v
                     [AWS S3] --> [GD] --> [EventBridge] --> [Lambda forwarder] --> [API] --> [DB]

---

## Error & Status Contract (recommended)

For any file upload:
- return a stable ID immediately
- expose a status endpoint or include status in normal reads
- statuses:
  - PENDING_SCAN
  - SCANNING
  - CLEAN
  - REJECTED
  - FAILED

Frontend:
- show progress/state
- display actionable errors
- allow retry when policy allows

---

## Outputs & Artifacts

- Store run outputs under `logs/` (ignored by default in git).
- Summarize key takeaways in `docs/ai/MEMORY.md`.
- Record architectural/security decisions in `docs/ai/DECISIONS.md`.