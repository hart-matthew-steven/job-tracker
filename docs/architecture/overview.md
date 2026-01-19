# Architecture Overview

This document describes the high-level architecture for Job Tracker, including component boundaries, AWS usage, development exposure via ngrok, and file-scanning via ClamAV.

The intent is to keep the root README concise while documenting real system shape and security posture here.

---

## Goals

- Clear separation between frontend, backend, documentation, logs, and one-off scripts
- Predictable, maintainable architecture that scales from local dev to AWS
- Secure file handling (untrusted uploads are scanned before acceptance/processing)
- Keep AI-assisted development deterministic (small scopes, versioned “memory” docs)

Non-goals:
- Document every AWS/IAM detail here (those belong in deeper, service-specific docs if needed)
- Over-abstract or “enterprise-ify” a personal project

---

## Components

### Frontend (React + Vite)
- Presents UI for job applications, statuses, notes, and related metadata
- Calls the backend via a centralized API client
- Runs locally in dev (`npm run dev`)
- Deployed separately from the backend in production (implementation can vary)
- Public marketing routes (`/` + `/demo/board`) showcase the product without hitting backend APIs; `/demo/board` renders a static, read-only board preview for prospects who have not created an account yet.
- Navigation shell keeps primary actions (global search, “Create job”) in the header for every breakpoint. On mobile the drawer is nav-only; keeping actions inline prevents workflow divergence between devices.

### Backend API (Python)
- Owns business logic and data persistence
- Exposes a REST API to the frontend
- Handles auth/session logic (if applicable)
- Integrates with AWS services for storage and background processing
- Coordinates file upload validation and anti-malware scanning

### Billing & AI Credits (Stripe + OpenAI)
- The backend keeps prepaid “AI Credits” in two tables: `credit_ledger` (balances) and `ai_usage` (per-request audit trail). The DB is the source of truth; Stripe merely funds balances and OpenAI never bills us directly.
- Credit balances are stored as integer cents (1 USD = 100 credits). Doing all math in integers prevents float rounding drift and keeps idempotent reconciliations predictable when real money is involved.
- Every ledger row records `source` (`stripe`, `admin`, `promo`, `usage`, etc.) plus an optional `source_ref`. `(user_id, source_ref)` and `(user_id, idempotency_key)` are unique so Stripe webhooks, admin tooling, and AI usage can retry safely without double-crediting.
- Stripe Checkout is the only way to purchase credits. Users are linked to Stripe customers (`users.stripe_customer_id`), and every purchase references a configured pack (`STRIPE_PRICE_MAP=pack:price_id:credits`). The backend accepts only a `pack_key`, resolves the Stripe price + credit quantity, and writes that metadata into the Checkout session so the webhook can’t be spoofed.
- Every webhook payload is written to `stripe_events` before any balance mutation. We track `status` (`pending`, `processed`, `skipped`, `failed`), the raw payload, and error text for observability/idempotency. A rerun that hits the `stripe_event_id` unique constraint simply returns `200 OK` without touching balances.
- Credits are minted exclusively by signed `checkout.session.completed` events where `payment_status=paid`. The handler runs inside a transaction: insert `stripe_events` → mint `credit_ledger` entry (with `pack_key`, checkout/payment intent ids, per-user `idempotency_key`) → mark status `processed|skipped`. Any exception sets `status=failed`, stores the error, and returns HTTP 500 so Stripe retries.
- Spending/reservations:
  - `reserve_credits(...)` inserts `entry_type=ai_reserve` rows (status `reserved`, correlation id) after locking the user row. This immediately reduces the available balance so overlapping AI requests cannot double spend.
  - `finalize_charge(...)` first releases the hold (`ai_release`) then posts the actual cost (`ai_charge`). `refund_reservation(...)` instead writes `ai_refund` and marks the hold refunded. Every step has its own `idempotency_key`, so retries simply read the existing ledger entries.
  - If the balance would go negative we raise HTTP 402 and never touch the ledger. `/ai/chat` tokenizes prompts with `tiktoken`, budgets `AI_COMPLETION_TOKENS_MAX` completion tokens, applies the buffer (`AI_CREDITS_RESERVE_BUFFER_PCT`), and only then calls OpenAI, so paid work never starts unless funds are available.
- The OpenAI orchestration layer estimates token usage, over-reserves with `AI_CREDITS_RESERVE_BUFFER_PCT`, calls `OpenAIClient`, then settles the reservation with the actual amount. If OpenAI returns more tokens than the reservation the entire hold is refunded, the response is discarded, and HTTP 500 is returned so the client can retry.
- AI conversations are durable:
  - `ai_conversations` table stores conversation metadata (`user_id`, `title`, timestamps). `ai_messages` stores both user and assistant turns plus optional token/credit metadata.
  - `AIConversationService` trims history to `AI_MAX_CONTEXT_MESSAGES`, enforces `AI_MAX_INPUT_CHARS`, writes the user message, and delegates to `AIUsageOrchestrator`. Successful completions create the assistant message + `ai_usage` row (linked via `conversation_id`/`message_id`).
  - Conversation summaries keep long threads usable. After configurable thresholds (`AI_SUMMARY_MESSAGE_THRESHOLD`, `AI_SUMMARY_TOKEN_THRESHOLD`) the service batches the latest turns (bounded by `AI_SUMMARY_CHUNK_SIZE`), calls OpenAI (using `AI_SUMMARY_MODEL` when set), and stores the result in `ai_conversation_summaries`. `_build_context` injects the latest summary as a system message so downstream prompts retain historical context without sending hundreds of messages. `GET /ai/conversations/{id}` exposes `context_status` (token budget/usage/percent + last summary timestamp) and `latest_summary` so the frontend can display a Cursor-style context meter. Tunables live in `.env` (`AI_CONTEXT_TOKEN_BUDGET`, `AI_SUMMARY_MAX_TOKENS`, etc.).
  - New endpoints (`POST/GET /ai/conversations`, `GET /ai/conversations/{id}`, `POST /ai/conversations/{id}/messages`) expose the data. Responses include the latest messages, credits debited/refunded, and the remaining balance so the frontend never recalculates money locally.
- Per-user guardrails live in `app/services/limits.py`: `AI_REQUESTS_PER_MINUTE` rate limiter + `AI_MAX_CONCURRENT_REQUESTS` concurrency limiter. Exceeding either returns HTTP 429 before credits are touched. OpenAI calls include correlation ids (`X-Request-Id` or generated) and jittered retries up to `AI_OPENAI_MAX_RETRIES`.
- Request-level rate limiting (for `/auth/cognito/*`, `/ai/*`, and document upload presigns) is implemented via DynamoDB (`jobapptracker-rate-limits`). Each request increments `{pk=user:{id}|ip:{addr}, sk=route:{key}:window:{seconds}}` with TTL expiry so App Runner’s multiple instances share a consistent budget without running Redis/ElastiCache.
  - Settlements handle overruns safely: if actual cost > reserved, we finalize the reserved amount and attempt to `spend_credits` for the delta. If the user lacks funds we refund the entire reservation and return HTTP 402—no negative balances or silent absorption.
- Operational controls:
  - Every rate-limit decision emits a structured JSON log with `{user_id, route, method, limiter_key, window_seconds, limit, count, remaining, reset_epoch, decision}` so CloudWatch/Log Insights can slice by user, route, or limiter bucket without parsing free-form text.
  - Admin-only tools hang off `/admin/rate-limits/*` and require `users.is_admin=true` (enforced by `require_admin_user`). Status/Reset/Override endpoints query or mutate the DynamoDB table directly and are the approved way to unblock a legitimate user without relaxing global settings.
  - Overrides write a short-lived `sk=override:global` item with `{request_limit, window_seconds, expires_at}` which is checked before the standard route key. TTL (`expires_at`) is required, so temporary exceptions self-heal without manual cleanup.

### AWS (Production Infrastructure)
The project assumes AWS-managed services are used for:
- Storage (e.g., uploads, generated artifacts)
- Persistence (DB choice can vary; architecture keeps it swappable)
- Background processing (queues/jobs/events)
- Observability/logging (as needed)

The exact services may evolve, but the architectural principle is stable:
- the backend remains the “control plane”
- AWS services are used for durability, security, and scalability

---

## Development vs Production

### Development
- Frontend runs locally on Vite’s dev server
- Backend runs locally (or in a local container)
- ngrok may be used to expose the backend temporarily for:
  - webhook testing
  - integration testing against external systems
  - mobile testing without local network configuration

Development principle:
- expose the minimum surface area needed
- keep secrets out of the repo
- keep logs and outputs in `logs/`

### Production
- Backend runs behind AWS-managed networking controls
- External access to backend is via a stable HTTPS endpoint
- Upload/storage/queues are AWS-managed for durability and security

Production principle:
- secure by default
- least privilege access to storage/queues
- scanned file workflow enforced

---

## File Scanning (AWS GuardDuty Malware Protection for S3)

Uploaded files are treated as untrusted input.

High-level approach:
- Files are not considered "accepted" or "safe" until scanned
- Scanning is performed by **AWS GuardDuty Malware Protection for S3** (AWS-managed service)
- A file that fails scanning is marked as INFECTED and download is blocked

Architecture:
- Files are uploaded to S3 via presigned URLs
- GuardDuty scans objects automatically (no file download by us)
- EventBridge forwards GuardDuty findings to a Lambda forwarder
- Lambda extracts `document_id` from S3 key and calls backend internal callback
- Backend updates DB `scan_status` (CLEAN/INFECTED/ERROR) and blocks downloads unless CLEAN

This project documents scanning behavior in more detail in:
- `docs/architecture/security.md`
- `docs/architecture/data-flow.md`

---

## Observability & Outputs

- Human-readable documentation belongs in `docs/`
- Script output and one-off run results belong in `logs/`
- Disposable scripts belong in `temp_scripts/`

If a log file is useful long-term:
- commit it intentionally
- treat it as an artifact, not canonical documentation

---

## AI-Assisted Development Conventions

This repo uses a versioned, explicit approach to AI context:
- Durable summaries go in `docs/ai/MEMORY.md`
- Decisions and rationale go in `docs/ai/DECISIONS.md`
- A repo map lives in `docs/ai/MAP.md`

This is intentional:
- it keeps costs predictable
- it avoids “mystery context”
- it makes work auditable and reproducible