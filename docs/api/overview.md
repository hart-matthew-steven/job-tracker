# API Overview

This document describes the Job Tracker backend API at a consumer level:
- authentication (if enabled)
- common request/response conventions
- error format
- pagination/filtering (if enabled)
- where to find endpoint-specific details

For endpoint inventory and examples, see:
- `docs/api/endpoints.md`

---

## Base URL

Development:
- Backend runs locally (e.g., `http://localhost:<port>`)
- May be exposed via ngrok for webhook/integration testing (dev only)

Production:
- Served behind AWS-managed networking and HTTPS

---

## Authentication

- Mechanism: Cognito Option‑B (Backend-for-Frontend). Clients talk only to `/auth/cognito/*`; the backend calls Cognito IDP APIs on their behalf.
- Tokens: `/auth/cognito/login` returns the raw Cognito `access_token`, `id_token`, `refresh_token`, `expires_in`, `token_type`. SPAs store access/id tokens in memory + `sessionStorage` and refresh tokens in `sessionStorage` only.
- Headers: every protected endpoint requires `Authorization: Bearer <cognito-access-token>`.
- Email verification is enforced by the backend (`/auth/cognito/verification/{send,confirm}`) before other APIs can be used.
- CAPTCHA: `/auth/cognito/signup` requires a valid Cloudflare Turnstile token (`turnstile_token`), verified server-side.

Notes:
- Never document secret values. Reference env var names only.
- For flow specifics see `docs/api/auth.md`.

---

## Request/Response Conventions

### Content Types
- JSON request/response bodies unless explicitly noted.
- File uploads use multipart/form-data (if implemented).

### Common Headers
- `Content-Type: application/json` for JSON requests
- `Authorization: Bearer <token>` (if auth enabled)

### Resource IDs
- IDs are returned as strings unless otherwise specified.

---

## Error Format (recommended)

Errors should be consistent and actionable. Recommended structure:

- `error`: stable error code (string)
- `message`: user-readable message
- `details`: optional structured info for debugging

Example:

    {
      "error": "VALIDATION_ERROR",
      "message": "Invalid request payload",
      "details": { "field": "status" }
    }

---

## File Uploads (if enabled)

High-level expectations:
- Uploaded files are treated as untrusted until scanned.
- File status should be explicitly represented (PENDING_SCAN, CLEAN, REJECTED, etc.)
- Upload endpoints should return a stable file ID immediately and allow status polling.

For flow details, see:
- `docs/architecture/data-flow.md`
- `docs/architecture/security.md`

---

## Rate Limiting

- Protected routes call `require_rate_limit(route_key, limit, window_seconds)` before hitting business logic. Rows are stored in DynamoDB as `{pk=user:{id}|ip:{addr}, sk=route:{key}:window:{seconds}}` with `window_start`, `count`, `request_limit`, `window_seconds`, `route_key`, `item_type`, and TTL (`expires_at`). Overrides live at `sk=override:global` with their own TTL so temporary exceptions self-expire.
- Every decision emits a structured JSON log (`user_id`, `route`, `http_method`, `limiter_key`, `window_seconds`, `limit`, `count`, `remaining`, `reset_epoch`, `decision`). When a customer reports HTTP 429 you can search the logs by `user_id` or limiter key to see exactly which window fired.
- Admin-only tooling:
  - `GET /admin/rate-limits/status?user_id=<id>` lists all active limiter items (counters + overrides) for that user.
  - `POST /admin/rate-limits/reset` deletes the rows so the next request starts fresh.
  - `POST /admin/rate-limits/override` writes a short-lived override (`limit`, `window_seconds`, `ttl_seconds`) that applies before normal route keys.
  - **Promotion is manual by design.** Run `UPDATE users SET is_admin=true WHERE email='you@example.com';` from psql to grant access; there is no public “make me admin” endpoint.
- Exceeding the configured budget (e.g., `AI_RATE_LIMIT_MAX_REQUESTS` within `AI_RATE_LIMIT_WINDOW_SECONDS`) yields HTTP 429 and sets the `Retry-After` header. Per-IP fallback ensures anonymous callers are throttled even without Cognito identity.
- Configuration knobs live in `.env.example` (`RATE_LIMIT_ENABLED`, `DDB_RATE_LIMIT_TABLE`, default + AI-specific window/limit values). Local dev keeps the limiter disabled unless you explicitly enable it with AWS credentials.

---

## Bundled responses

To keep the SPA snappy on high-latency networks, some routes intentionally return multiple resource types at once. Key examples:

- `GET /jobs/{job_id}/details`: returns the job, notes, interviews, and activity slice for the drawer.
- `GET /jobs/board`: returns an array of statuses plus board cards (with `priority`, `next_action_at`, `last_action_at`, `needs_follow_up` hints) so the Kanban can hydrate in one round trip.
- `GET /jobs/search`: returns board cards for global search / command palette results.
- `GET /ai/conversations/{conversation_id}`: returns the requested page of messages and augments the payload with `context_status` (token budget/usage/percent + last summary timestamp) and `latest_summary` so the UI can render a Cursor-style context meter without extra requests.
- `POST /jobs/`: create a job from anywhere (desktop or mobile). The SPA now surfaces the Create button directly in the header on small screens, but it still calls this same endpoint behind the scenes; no additional mobile-specific API exists.

- `job`: `JobApplicationOut`
- `notes`: ordered newest → oldest
- `interviews`: user-scoped interview rows
- `activity`: timeline entries (default limit 20, clamp 1–200 via `activity_limit`)

These endpoints replace several sequential calls, but the underlying single-resource routes remain available for incremental updates (e.g., deleting a note still re-fetches `/jobs/{id}/notes` for truth).

---

## Updating this document

This file should be updated when:
- auth scheme changes
- response/error formats change
- cross-cutting API conventions change