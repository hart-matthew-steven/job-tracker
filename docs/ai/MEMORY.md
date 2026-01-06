# docs/ai/MEMORY.md
# Project Memory (Authoritative)

Purpose: durable, repo-managed project state so future sessions can resume reliably.
Keep it concise, factual, and employer-facing.

## Current Implementation Status
### Frontend (`frontend-web/`)
- App shell with responsive nav and account menu.
- Auth pages: Login / Register / Verify (verify page triggers resend/confirm without needing to log in first).
- Register page embeds Cloudflare Turnstile (invisible/managed mode). Tokens are fetched/reset per submit and appended to the `/auth/cognito/signup` payload.
- Cognito currently relies on the default Cognito email sender (verification/reset emails come from AWS). A Pre Sign-up Lambda auto-confirms users and keeps Cognito from sending codes while we prep a future custom email flow; the SPA routes new signups straight to `/verify` so they can request/confirm the Resend code before logging in.
- The backend now enforces email verification via `/auth/cognito/verification/{send,confirm}` (hashed 6-digit codes, TTL, cooldown, Resend delivery). Middleware blocks everything except the verification endpoints/logout/`GET /users/me` until `users.is_email_verified` is true. Successful confirmation also calls Cognito `AdminUpdateUserAttributes` with `Username=cognito_sub` so `email_verified=true` propagates to AWS/iOS clients.
- Register + Change Password now share a password policy helper and inline `PasswordRequirements` list to block weak passwords before submission; backend error violations render in the UI.
- Jobs page collapse state is persisted server-side; toggling a card calls `PATCH /users/me/ui-preferences` so the preference follows users across browsers/devices.
- `AuthProvider` centralizes token storage and now enforces a client-side idle timeout (default 30 minutes, configurable via `VITE_IDLE_TIMEOUT_MINUTES`, min 5). Any keyboard/mouse/touch/scroll/visibility event resets the timer; when it expires the SPA clears tokens and redirects to `/login`.
- Jobs page:
  - Server-side search + filters (q, tags, multi-select statuses)
  - Saved views UI
  - Timeline + interviews panels (timeline lives in a fixed-height scroll container and automatically fetches older activity as you scroll)
  - Auto-refresh (controlled by user setting)
  - Defaults: applies account default sort/view on first load; “Use defaults” button to re-apply
- Profile + Change Password wired to backend APIs.
- Landing page hero copy no longer references “private alpha” or Jira, and the “View demo board” CTA sends visitors to `/demo/board`, a read-only board preview rendered entirely in the browser so they can experience the kanban UX without signing in.
- AppShell keeps the search affordance and “Create job” CTA visible in the header even on mobile breakpoints; the drawer is nav-only. This ensures primary actions stay one tap away regardless of screen size.
- Settings page wired to backend:
  - Auto refresh frequency
  - Jobs default sort/view
  - Theme (dark/light/system) applied app-wide (Tailwind `dark` class)
  - Data retention (UI-only): jobs older than N days are hidden in Jobs + Dashboard (data stays in DB)

### Backend (`backend/`)
- FastAPI + SQLAlchemy + Alembic migrations.
- Auth model:
  - Cognito Option B (no Hosted UI). `/auth/cognito/*` implements signup/confirm/login/challenge/MFA/refresh/logout, and every request passes through the JWKS verifier in `app/auth/cognito.py`.
  - Access/id tokens stay in memory + sessionStorage on the client; refresh tokens stay in sessionStorage only and flow through `/auth/cognito/refresh` (Cognito `REFRESH_TOKEN_AUTH`).
  - Signup is protected by Cloudflare Turnstile (Chunk 8). `CognitoSignupIn` includes `turnstile_token`; backend verification posts to Cloudflare’s `/siteverify` endpoint and fails closed if keys are missing. Only signup is gated.
- Users:
  - `users` table stores `email`, `name`, `cognito_sub`, `auth_provider`. Legacy password/email-verification columns were removed by `cognito_cutover_cleanup`.
  - Identity middleware JIT-provisions a row on first Cognito login and attaches `request.state.user` for authorization checks.
- Settings stored on user with `/users/me/settings` GET/PUT:
  - `auto_refresh_seconds`, `theme`, `default_jobs_sort`, `default_jobs_view`, `data_retention_days`
- Additional JSON preferences (`users.ui_preferences`) store UI state; `/users/me/ui-preferences` lets clients persist toggles (e.g., notes/interviews/timeline/documents collapsed flags). Identity middleware exposes the data as part of `GET /users/me`.
- `GET /jobs/{job_id}/details` bundles `{job, notes, interviews, activity: { items, next_cursor }}` so the Jobs page hydrates via a single round trip. Legacy per-resource routes remain for incremental updates after mutations or to fetch additional pages (e.g., `/jobs/{job_id}/activity?cursor_id=...`).
- Email delivery / verification:
  - `/auth/cognito/verification/send` and `/confirm` are public (no login required). Codes are salted SHA-256 hashes with TTL/cooldown/attempt caps, delivered via Resend (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`).
  - Identity middleware blocks all other APIs with `403 EMAIL_NOT_VERIFIED` until `users.is_email_verified` is true; confirmation also calls Cognito `AdminUpdateUserAttributes` (`Username=cognito_sub`, `email_verified=true`).
- Password policy:
  - `PASSWORD_MIN_LENGTH` (default 14) enforced at signup via `ensure_strong_password`. Requirements: length, upper/lowercase, number, special char, no email/name substrings, denylist.
- Database access:
  - Runtime API connects with `DB_APP_USER` / `DB_APP_PASSWORD` (CRUD-only).
  - Alembic migrations run with `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD` (DDL).
  - Config exposes both URLs (`database_url`, `migrations_database_url`) to keep least privilege enforced.
- Optional integrations:
  - `GUARD_DUTY_ENABLED` gates the GuardDuty malware callback; local/dev environments typically leave it disabled.
- Deployment:
  - Production backend runs on AWS App Runner behind `https://api.jobapptracker.dev`, pulling ECR images built with `docker buildx --platform linux/amd64` and loading secrets from AWS Secrets Manager.
  - GitHub Actions handle production deploys: `backend-deploy.yml` builds/pushes images and calls `scripts/deploy_apprunner.py`; `frontend-deploy.yml` builds the Vite SPA, uploads a versioned release to S3, promotes it, updates metadata, invalidates CloudFront, and runs health checks via `scripts/deploy_frontend.py`.
- Documents:
  - Presigned S3 upload flow implemented (presign → upload to S3 → confirm). GuardDuty Malware Protection + Lambda forwarder update `scan_status` before downloads are allowed. The Lambda now reads `DOC_SCAN_SHARED_SECRET` from AWS Secrets Manager via `DOC_SCAN_SHARED_SECRET_ARN` (not plain env text) before calling `/jobs/{job_id}/documents/{document_id}/scan-result`.
- Debug endpoints `/auth/debug/token-info` + `/auth/debug/identity` remain dev-only. Authorization across the app depends on Cognito access tokens + DB ownership checks; there is no custom JWT mode anymore.
- Billing:
  - `credit_ledger` (integer cents) + `stripe_events` (raw payload, `status`, `processed_at`, `error`) are the source of truth for prepaid credits.
  - `STRIPE_PRICE_MAP` configures credit packs (`pack_key:price_id:credits`). `/billing/stripe/checkout` only accepts a `pack_key` and stamps metadata (`user_id`, `pack_key`, `credits_to_grant`, `environment`) into the Checkout Session so the webhook can mint credits deterministically.
  - `/billing/stripe/webhook` validates the signature, inserts `stripe_events` (`status=pending`), runs the handler transactionally, writes to `credit_ledger` with pack/session metadata, and updates status to `processed|skipped|failed`. Failures capture the error and return HTTP 500 so Stripe retries.
  - `/billing/me` exposes the balance + Stripe customer id + the latest ledger entries; `/billing/packs` surfaces the configured packs for the frontend.

## What Is Working
- Cognito signup → confirm → login → MFA setup/verify → authenticated app access.
- Logout + auth navigation guards.
- Profile fetch.
- Password policy helper reused for Cognito signup validations.
- DB-backed settings (auto refresh + jobs defaults + theme + data retention preference).
- Job listing + detail view (notes + documents panels) with auth.
- Tags end-to-end (stored on jobs; filterable in UI; persisted in saved views).
- Job activity timeline (notes/documents/status updates).
- Job interviews CRUD in UI + backend.
- Stripe prepaid credits: pack-based Checkout, webhook-driven credit grants, `/billing/me`/`/billing/credits/*` APIs, and webhook idempotency backed by `stripe_events`.

## Partially Implemented / Deferred
- Offer tracking (explicitly deferred / skipped for now).
- CI quality gate (tests/lint/typecheck required before merge) partially implemented:
  - GitHub Actions workflows added (backend + frontend)
  - Branch protection still needs to be enabled in GitHub settings to block merges
- Deployment safeguards:
  - CI/CD now auto-deploys backend + frontend; next steps are staged environments, alerting, and richer observability/rollback telemetry.
- Document malware scanning fully implemented:
  - **AWS GuardDuty Malware Protection for S3** is the production scan engine.
  - EventBridge triggers a Lambda forwarder (`lambda/guardduty_scan_forwarder/`).
  - Lambda extracts `document_id` from S3 key and calls backend internal callback.
  - Verdict source of truth is the S3 object tag `GuardDutyMalwareScanStatus`; if the EventBridge event does not include tags, the Lambda calls S3 `GetObjectTagging` to read the verdict.
  - Backend updates DB `scan_status` (PENDING → CLEAN/INFECTED/ERROR) and blocks downloads unless CLEAN.
  - Frontend polls for status updates and displays scan state.
  - Backend can still be exposed via ngrok for local dev/testing.
- Production AWS deployment hardening is in progress: runtime now lives on App Runner, but logging/alerting/secret rotation automation is still pending.
- Feature roadmap:
  - AI copilot to tailor resumes vs job descriptions, generate cover/thank-you letters, and upload artifacts to the relevant job automatically.
  - Multi-factor authentication and passkey support; long-term, Face ID login for the future iOS client.

## Known Issues / Notes
- SES deliverability: verification emails may land in spam depending on sender identity/domain posture.
- Tailwind v4 note: `dark:` is configured to follow the `.dark` class via `@custom-variant` in `frontend-web/src/index.css` (not media-based).

## Recent Changes (High Signal)
- Stripe billing hardening:
  - Added `stripe_customer_id` linkage, `STRIPE_PRICE_MAP` parser, `/billing/packs`, and `/billing/me`.
  - Checkout now accepts only `pack_key`; metadata instructs the webhook how many credits to mint.
  - Webhooks use transactional inserts into `stripe_events` (with status/error fields) plus ledger entries that capture pack key + Stripe ids; duplicates short-circuit, failures mark the row and return HTTP 500 for retries.
  - Tests cover checkout metadata, webhook idempotency/failure, new billing APIs, and pack listing.
- Idle-time logout: the frontend now clears Cognito tokens after ~30 minutes of inactivity (configurable via `VITE_IDLE_TIMEOUT_MINUTES`; min 5) to reduce risk from abandoned tabs without changing Cognito’s refresh token policy.
- Mobile AppShell parity: search + Create now live in the header on every breakpoint, eliminating the need to open the drawer to add roles on phones/tablets. Drawer tests cover the status-change flow to guard against regressions.
- Jobs page performance: added `GET /jobs/{job_id}/details` to bundle job + notes + interviews + activity, replacing four sequential requests on every selection.
- Timeline pagination: `/jobs/{job_id}/activity` now returns `{items,next_cursor}`, and the frontend timeline uses an infinite-scroll container to append older entries seamlessly.
- Chunk 9 (rolled back): Cognito Custom Message Lambda removed; Cognito default emails restored while a new plan is evaluated.
- Chunk 10: Added Pre Sign-up Lambda (auto-confirm, disable `autoVerifyEmail`) so signup doesn’t depend on Cognito email codes.
- Chunk 11: App-enforced verification (hashed codes in DB, Resend delivery, Cognito admin sync, middleware 403) with updated frontend flow (signup redirects to `/verify`, public resend/confirm endpoints, redirect on 403 `EMAIL_NOT_VERIFIED`).
- Chunk 8: Signup is now protected by Cloudflare Turnstile (`turnstile_token` field, backend verification, new env vars). Tests cover success/failure/missing token paths.
- TypeScript migration completed for `frontend-web/` (`tsc --noEmit` passes; `allowJs=false`; no JS/JSX in `src/`).
- Feature buildout completed: statuses/pipeline, saved views, search/filters, tags, timeline, interviews.
- Settings expansion completed: defaults, auto refresh, theme (dark/light/system), data retention (UI-only hiding).
- Phase 4 refactor completed (for now):
  - Frontend: broke up `JobsPage.tsx` into `src/pages/jobs/*` modules and introduced shared UI class helpers in `src/styles/ui.ts`.
  - Backend: centralized job ownership + tag helpers in `app/services/jobs.py`.
  - Backend: centralized refresh-token/cookie helpers in `app/services/refresh_tokens.py` and document validation/policy helpers in `app/services/documents.py`.
- Phase 5 completed: standardized backend API error shape to match `docs/api/error-format.md`.
 - Phase 6 completed (for now): automated tests added for backend + frontend.
  - Backend:
    - `pytest` harness with in-memory SQLite in `backend/tests/conftest.py`
    - Coverage includes auth flows, jobs CRUD/filtering, ownership isolation, saved views, documents pipeline (presign/confirm/scan/download), activity payload correctness, API error shape contract, and rate limiting
  - Frontend:
    - `vitest` + React Testing Library with cleanup in `frontend-web/src/setupTests.ts`
    - Coverage includes auth pages, routing guards, AppShell navigation/logout, Jobs flows (filters, saved views, create job), notes, documents, settings, and auto-refresh pause logic
 - Phase 7 started: CI quality gate wiring (GitHub Actions)
  - Workflows: `.github/workflows/ci-backend.yml` and `.github/workflows/ci-frontend.yml`
  - Setup guide: `docs/ci/github-actions.md` (includes branch protection steps)

- Malware scanning pipeline implemented (S3 → GuardDuty → EventBridge → Lambda → backend callback):
  - DB fields on `job_documents`: `scan_status`, `scan_checked_at`, `scan_message`, `quarantined_s3_key` (last field unused for GuardDuty)
  - Backend internal callback: `POST /internal/documents/{document_id}/scan-result` (shared-secret header: `x-doc-scan-secret`)
  - Lambda forwarder: `lambda/guardduty_scan_forwarder/` (EventBridge-triggered; parses GuardDuty findings; calls backend)
  - Architecture docs: `docs/architecture/security.md`, `docs/architecture/data-flow.md`
  - **Migrated from ClamAV** (removed SQS, EFS-based definitions, quarantine logic) to **AWS GuardDuty Malware Protection for S3**.
- Legacy email service removed:
  - Deleted Resend/SES/SMTP helpers and env vars; future notification work will live in Cognito-triggered Lambdas.
- Hosting upgrade:
  - Backend Dockerfile + README updated for App Runner (ECR build/push commands, `--platform linux/amd64` requirement, secrets from AWS Secrets Manager, health checks hitting `/health`).
- CI/CD automation:
  - `backend-deploy.yml` + `scripts/deploy_apprunner.py` build/push the API image, update App Runner, wait for health, and roll back on failure.
  - `frontend-deploy.yml` + `scripts/deploy_frontend.py` version frontend builds in S3, promote releases, invalidate CloudFront, and keep rollback metadata in `_releases/current.json`.
- GuardDuty gating:
  - Introduced the `GUARD_DUTY_ENABLED` feature flag so local Docker can run without GuardDuty; added noop handlers + test coverage.
- Password policy:
  - `ensure_strong_password` helper + shared frontend UI enforce uppercase/lowercase/number/special/no email/name.
  - Rotation-specific columns were removed once Cognito became the sole auth provider.

## Utilities
- Dev DB reset + S3 cleanup script: `temp_scripts/reset_dev_db.py`
  - Requires `ENV=dev`
  - Interactive confirmation unless `--yes`
  - Writes a timestamped log to `logs/reset_dev_db_*.log`
