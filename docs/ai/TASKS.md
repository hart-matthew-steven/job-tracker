# docs/ai/TASKS.md
# Tasks

## In Progress
- Phase 2B: Artifact history + diff surfacing
  - Backend endpoints (`/ai/artifacts/.../history`, `/ai/artifacts/{id}/diff`) plus tests/docs are merged.
  - Next: expose the picker/diff UI in the assistant and add regression tests once the frontend lands.
- Phase 7: CI quality gate (block merges when checks fail):
  - GitHub Actions workflows added
  - Branch protection (required checks) needs to be enabled in GitHub UI

### Cognito Auth Migration
- [Migration Plan](docs/architecture/security.md#cognito-authentication-migration-plan)
- Work is split into tightly scoped chunks:
  - **Chunk 0** (completed): docs + placeholders only
  - **Chunk 1** (completed): backend read-only Cognito JWT verifier (historical toggle removed; backend now always enforces Cognito)
  - **Chunk 2** (completed): unified identity model (`Identity` dataclass), `/auth/debug/identity`
  - **Chunk 3** (retired): original profile gate removed in Chunk 5
  - **Chunk 4** (completed): backend authorization + JIT provisioning; Cognito became the primary auth source
  - **Chunk 5** (completed): remove profile gate + add Cognito Option B (BFF) endpoints for signup/login/MFA (no redirects)
  - **Chunk 6** (completed): deterministic challenge handling + required TOTP setup/verify flows
  - **Chunk 7** (completed): production cutover — only Cognito tokens accepted, refresh endpoint wired, SPA stores tokens in sessionStorage/in-memory
  - **Chunk 8** (completed): Cloudflare Turnstile bot protection on signup (frontend widget + backend verification before calling Cognito)
  - **Chunk 9** (rolled back): Custom Message Lambda removed; default Cognito emails restored
  - **Chunk 10** (completed): Pre Sign-up Lambda auto-confirms users and disables Cognito email verification
  - **Chunk 11** (completed): App-enforced email verification (hashed codes + TTL/cooldown in DB, Resend delivery, Cognito `AdminUpdateUserAttributes` sync, middleware 403) with public resend/confirm endpoints so signup flows through `/verify` before first login
- Future chunks: passkeys, native iOS flows, AI usage/billing attribution, security hardening.

## Next
- Deployment safeguards:
  - Add branch protection / required checks so CI must pass before backend/frontend deploy workflows run automatically.
  - Add monitoring/alerting around the new pipelines (health check failures, rollback notifications).
- Observability:
  - Decide on log aggregation + metrics/alerts for App Runner and CloudFront/S3 so production incidents are easier to triage.

## Later
- Feature enhancements:
  - AI assistant to compare resumes vs job descriptions, suggest tailored edits, generate cover/thank-you letters, and upload the resulting files to the relevant job automatically.
  - Multi-factor authentication + passkey support, with an eventual iOS app that can leverage Face ID for login.
  - Offer tracking revamp once higher-priority workflows ship.
- Deployment polish:
  - Additional AWS hardening (observability, alerting, secret rotation schedule, staged environments).

## Completed
- Backend & frontend deployment automation:
  - `backend-deploy.yml` builds/pushes the API image, assumes AWS role via OIDC, and calls `scripts/deploy_apprunner.py` for zero-downtime deploys with rollback + health checks.
  - `frontend-deploy.yml` builds the Vite SPA, versions releases in S3 via `scripts/deploy_frontend.py`, promotes them, invalidates CloudFront, and records release metadata for rollbacks.
- UX polish (2026-01-05):
  - Mobile AppShell now mirrors desktop by keeping the search pill and “Create job” CTA in the header; the drawer is nav-only.
  - Added regression tests around the Board Drawer’s status change flow to ensure the drawer no longer flickers or reloads when saving.
- Landing page refresh + public demo board: `/` messaging no longer references “private alpha”/Jira, and `/demo/board` lets prospects explore a read-only kanban preview before creating an account.
- **Phase 8: Malware scanning pipeline** (GuardDuty Malware Protection for S3):
  - Migrated from ClamAV-based scanning to AWS GuardDuty for production reliability
  - Removed: ClamAV Lambda code, SQS triggers, EFS definitions, quarantine logic
  - Added: `lambda/guardduty_scan_forwarder/` (EventBridge → Lambda → backend callback)
  - Backend/frontend unchanged (same DB fields, internal callback API, download gating)
  - Architecture docs updated (`docs/architecture/security.md`, `docs/architecture/data-flow.md`)
- Legacy email service removed (now handled via Cognito + future Lambda trigger). Env vars (`EMAIL_*`, `RESEND_API_KEY`, `SMTP_*`) were deleted from config/docs.
- Strong password policy:
  - `PASSWORD_MIN_LENGTH` still enforced for Cognito signup helpers (`ensure_strong_password`).
  - Rotation-specific fields (`password_changed_at`, `token_version`, `PASSWORD_MAX_AGE_DAYS`) were removed during the Cognito cutover.
- Database credential split:
  - Replaced legacy `DB_USER`/`DB_PASSWORD` with `DB_APP_*` (runtime CRUD) and `DB_MIGRATOR_*` (DDL) env vars.
  - Alembic + docs + `.env.example` now point at the migrator URL; runtime engine stays on the least-privilege user.
- Phase 7: CI quality gate (GitHub Actions workflows for backend + frontend lint/test)
- Phase 6: Automated tests added (backend + frontend; comprehensive coverage)
- Phase 5: Standardize API error shape (align backend responses with `docs/api/error-format.md`)
- Phase 4: Refactor the frontend and backend codebases to be more production-ready (structure/readability/maintainability; preserve behavior)
- Phase 3: migrate `frontend-web/` to TypeScript (completed; `src/` has no JS/JSX, `allowJs=false`)
- Refactor frontend: split `frontend-web/src/App.tsx` (extract pages/components/hooks), add `src/routes/paths.ts`, and group job components under `src/components/jobs/`.
- Consolidate backend user/settings responses (use dedicated settings schema for `/users/me/settings`)
- Phase 2: dev reset script implemented: `temp_scripts/reset_dev_db.py` (guardrails, S3 cleanup, logs, `--yes`)
- Phase 4: Refactor the frontend and backend codebases to be more production-ready (structure/readability/maintainability; preserve behavior) (completed for now)
- Phase 5: Standardize API error shape (align backend responses with `docs/api/error-format.md`) (completed for now)
- Phase 6: Automated tests added (backend + frontend):
  - Backend: pytest suite in `backend/tests/` (includes auth flow, jobs/filters/activity, documents pipeline, saved views, ownership isolation, rate limiting)
  - Frontend: Vitest + React Testing Library suite in `frontend-web/src/**/*.test.tsx` covering auth, routing guards, Jobs flows (filters/saved views/create), documents, settings, and auto-refresh pause logic
- Feature buildout (personal-use focus):
  - Statuses + pipeline
  - Saved views
  - Search + filters
  - Tags
  - Timeline (job activity)
  - Interview tracking
- Settings expansion:
  - Defaults (Jobs default sort/view)
  - Auto refresh
  - Appearance (theme: dark/light/system via Tailwind `dark` class)
  - Hide jobs after N days (UI-only hiding; data stays in DB)

## Completed
- Phase 2A: Conversation summaries + context meter
  - `ai_conversation_summaries` table + migrations shipped; summaries auto-generate once token/message thresholds are hit and are injected into future prompts.
  - `GET /ai/conversations/{id}` now returns `context_status` (token budget/usage/percent + last summary timestamp) and `latest_summary`.
  - New env knobs documented: `AI_CONTEXT_TOKEN_BUDGET`, `AI_SUMMARY_MESSAGE_THRESHOLD`, `AI_SUMMARY_TOKEN_THRESHOLD`, `AI_SUMMARY_MAX_TOKENS`, `AI_SUMMARY_CHUNK_SIZE`, `AI_SUMMARY_MODEL`.
- DynamoDB rate limiter:
  - Replaced the SlowAPI decorators with `require_rate_limit(...)` backed by `jobapptracker-rate-limits` (PK `pk=user:{id}|ip:{addr}`, SK `route:{key}:window:{seconds}`, TTL `expires_at`).
  - Added env knobs `RATE_LIMIT_ENABLED`, `DDB_RATE_LIMIT_TABLE`, `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`, `RATE_LIMIT_DEFAULT_MAX_REQUESTS`, `AI_RATE_LIMIT_WINDOW_SECONDS`, `AI_RATE_LIMIT_MAX_REQUESTS`.
  - Tests stub DynamoDB (window rollover, TTL, limit enforcement) and verify `/ai/chat` returns HTTP 429 + `Retry-After`.
- AI conversations + guardrails:
  - Added `ai_conversations`/`ai_messages` tables, extended `ai_usage`, and implemented `AIConversationService` plus the DynamoDB-backed rate limiter (`require_rate_limit(...)`) and the in-memory concurrency limiter for per-user fan-out control.
  - New endpoints: `POST/GET /ai/conversations`, `GET /ai/conversations/{id}`, `POST /ai/conversations/{id}/messages`, each enforcing ownership, pagination, and prepaid credits.
  - Config grew `AI_MAX_INPUT_CHARS`, `AI_MAX_CONTEXT_MESSAGES`, `AI_REQUESTS_PER_MINUTE`, `AI_MAX_CONCURRENT_REQUESTS`, `AI_OPENAI_MAX_RETRIES`, and OpenAI retries now include jittered backoff + correlation ids.
  - Settlements charge the exact OpenAI cost: we finalize the reserved amount, bill any delta only if funds exist, otherwise refund and return HTTP 402. Tests exercise orchestrator delta handling, route behaviors (402/429/503), and limiter utilities.
- Refactor frontend: split `frontend-web/src/App.tsx` (extract pages/components/hooks), add `src/routes/paths.ts`, and group job components under `src/components/jobs/`.
- Consolidate backend user/settings responses (use dedicated settings schema for `/users/me/settings`)
- Phase 2: dev reset script implemented: `temp_scripts/reset_dev_db.py` (guardrails, S3 cleanup, logs, `--yes`)
- Stripe prepaid credits foundation hardened: `STRIPE_PRICE_MAP` pack config, `/billing/me` + `/billing/packs`, transactional webhook that updates `stripe_events` status + `credit_ledger` pack metadata. AI usage charging still to come (future chunk).
- Credits balance & guardrails (this step):
  - `/billing/credits/balance` now returns live balance + lifetime grant/spend totals and an `as_of` timestamp.
  - `credit_ledger` rows include a per-user `idempotency_key`, and `spend_credits/require_credits` lock the user row, enforce “no negative balances,” and raise HTTP 402 on insufficient credits. Debug spend endpoint is available only when explicitly enabled outside prod.
- Credits reservation layer:
  - Added `entry_type/status/correlation_id` columns so we can post `ai_reserve`, `ai_release`, `ai_charge`, and `ai_refund` rows.
  - `reserve_credits`, `finalize_charge`, and `refund_reservation` wrap the ledger writes with per-step idempotency keys plus DB-level locking.
  - `/ai/demo` exercises the full reserve/finalize/refund flow until OpenAI endpoints use the same helper.
- OpenAI usage integration:
  - `.env.example` now includes `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_CREDITS_RESERVE_BUFFER_PCT`, `AI_COMPLETION_TOKENS_MAX`.
  - `app/services/openai_client.py` wraps the SDK, while `app/services/ai_usage.py` handles tokenization via `tiktoken`, buffered reservations, settlement/refund, and idempotent replays backed by `ai_usage`.
  - `/ai/chat` enforces prepaid credits (tokenize → reserve → OpenAI → finalize/refund), returns usage stats + remaining balance, and surfaces HTTP 500/502 on overruns/provider failures. Tests cover reservation math, settlement scenarios, idempotency, and the new API.
