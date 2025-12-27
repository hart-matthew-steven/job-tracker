# docs/ai/DECISIONS.md
# Decisions (ADR-lite)

Record decisions that affect structure or long-term direction.

## Format
- Date:
- Decision:
- Rationale:
- Consequences:

---

## 2025-01-XX — Repo hygiene boundaries (docs/logs/temp scripts)
- Decision: Separate documentation, outputs/logs, and one-off scripts into top-level folders:
  - `docs/` for documentation
  - `logs/` for run output and artifacts
  - `temp_scripts/` for disposable scripts
- Rationale: Keep source code clean, reduce noise in commits, and make troubleshooting artifacts easy to locate.
- Consequences:
  - `logs/` and most of `temp_scripts/` are ignored by default in Git.
  - Useful artifacts must be committed intentionally.

---

## 2025-01-XX — Durable AI memory is repo-managed
- Decision: Durable “memory” is written to version-controlled docs instead of relying on hidden chat history.
- Rationale: Predictable context, lower costs, auditable work, easier onboarding for future readers.
- Consequences:
  - After meaningful changes, update `docs/ai/MEMORY.md`.
  - Record tradeoffs in this file.

---

## 2025-01-XX — Cursor context control
- Decision: Commit `.cursorignore` and `.cursor/rules/*` to define predictable AI scope and behavior.
- Rationale: Reduce accidental context bloat/cost and keep AI behavior consistent across machines.
- Consequences:
  - Changes to Cursor behavior are reviewable like code.

---

## 2025-12-18 — Auth: access token + refresh cookie
- Decision: Use Bearer JWT access tokens + HttpOnly refresh cookie with DB-stored refresh tokens.
- Rationale: Keeps API auth simple for the SPA while supporting refresh token rotation and revocation.
- Consequences:
  - `/auth/refresh` rotates refresh tokens and returns new access token.
  - `/users/me/change-password` revokes refresh tokens to force re-login.

---

## 2025-12-18 — Email verification delivery via SES (boto3)
- Decision: (Superseded) Initially send verification emails via AWS SES using `boto3` (SMTP remains optional fallback).
- Rationale: SES is a production-grade path for delivery and aligns with AWS hosting plans.
- Consequences:
  - Requires verified SES identity + appropriate IAM permissions/credentials.
  - Deliverability posture (SPF/DKIM/DMARC) should be addressed for public launch.

---

## 2025-12-21 — Email delivery providers: default to Resend; SES/Gmail supported
- Decision: Default email provider is `resend` when `EMAIL_PROVIDER` is unset. Supported providers are `resend`, `ses`, and `gmail` (SMTP). Treat `EMAIL_PROVIDER=smtp` as a legacy alias for `gmail`.
- Rationale: Resend provides an easy, modern integration for transactional emails; keeping SES and SMTP allows flexibility for AWS-hosted production and simple dev setups.
- Consequences:
  - Backend uses `FROM_EMAIL` for `resend`/`ses` only; Gmail/SMTP preserves `SMTP_FROM_EMAIL`.
  - Resend requires `RESEND_API_KEY`.
  - SES uses `AWS_REGION` for client initialization (no SES-specific region var).

---

## 2025-12-21 — Malware scanning: Migrated from ClamAV to AWS GuardDuty Malware Protection for S3
- Decision: Migrate from custom ClamAV-based scanning to **AWS GuardDuty Malware Protection for S3** for production reliability.
- Rationale: The ClamAV prototype encountered CDN definition update failures (403 cooldowns) from AWS egress IPs, requiring complex EFS + scheduled updater Lambda workarounds. GuardDuty is AWS-managed, eliminates CDN dependency, and requires no file downloads or custom scanning infrastructure.
- Consequences:
  - **Removed**: All ClamAV Lambda code (`lambda/clamav_scanner/`), SQS-based scan triggers, EFS-based definitions, quarantine copy/delete logic.
  - **Added**: Lightweight Lambda forwarder (`lambda/guardduty_scan_forwarder/`) that parses EventBridge events from GuardDuty and calls the existing backend internal callback.
  - **Backend unchanged**: DB scan fields (`scan_status`, `scan_checked_at`, `scan_message`) and internal callback API (`POST /internal/documents/{document_id}/scan-result`) remain the same integration point.
  - **Frontend unchanged**: Download gating and status display based on `scan_status` remain unchanged.
  - **AWS setup**: GuardDuty Malware Protection for S3 must be enabled; EventBridge rule forwards findings to the Lambda forwarder.
  - **Verdict source of truth**: GuardDuty marks S3 objects with the tag `GuardDutyMalwareScanStatus`. EventBridge events may not include tags, so the Lambda forwarder reads the verdict via S3 `GetObjectTagging` when needed (requires `s3:GetObjectTagging` scoped to the upload prefix).
  - **Infected files**: Remain in S3 but download is blocked by backend; no quarantine/copy needed (GuardDuty marks them).

## 2025-12-23 — Password policy + rotation enforcement
- Decision: Introduce configurable password strength + expiration rules (`PASSWORD_MIN_LENGTH` default 14, `PASSWORD_MAX_AGE_DAYS` default 90) enforced whenever passwords are set/changed. Track `password_changed_at` on users and surface `must_change_password` in auth responses so the frontend can gate access until users rotate.
- Rationale: Aligns with least-privilege goals and security review feedback; prevents weak credentials at creation time while letting existing accounts continue signing in until they update.
- Consequences:
  - New backend helper (`app/core/password_policy.py`) validates requirements and rejects weak passwords with structured `WEAK_PASSWORD` errors.
  - Alembic migration adds + backfills `password_changed_at`.
  - Login/refresh responses include `must_change_password`; `/users/me` mirrors it for UI gating.
  - Frontend uses shared helper (`src/lib/passwordPolicy.ts`) + `PasswordRequirements` component to block weak passwords client-side and display violations.
  - Docs + `.env.example` document the new env vars.

## 2025-12-23 — Split database credentials (runtime vs migrations)
- Decision: Replace the single `DB_USER`/`DB_PASSWORD` env vars with explicit runtime (`DB_APP_USER`/`DB_APP_PASSWORD`) and migrator (`DB_MIGRATOR_USER`/`DB_MIGRATOR_PASSWORD`) credentials. Runtime services connect via `settings.database_url`, while Alembic uses `settings.migrations_database_url`.
- Rationale: Enforces least privilege so the application pool cannot perform DDL or escalate schema, while migrations retain the permissions they need.
- Consequences:
  - Config defaults fall back so existing setups keep working, but `.env.example`/docs now list both credential sets.
  - Alembic `env.py` chooses the migrator URL (with app-user fallback for local prototyping).
  - Frontend/backends unaffected except for configuration; docs and tooling (e.g., `tools/generate_env_example.py`) reflect the split.

---

## 2025-12-24 — Production hosting via AWS App Runner + Secrets Manager
- Decision: Host the backend on AWS App Runner behind `api.jobapptracker.dev`, pull container images from ECR, and source sensitive configuration from AWS Secrets Manager (env injection) instead of local `.env` files.
- Rationale: App Runner provides managed HTTPS, health checks, autoscaling, and blue/green deploys without maintaining ECS clusters. Secrets Manager keeps JWT secrets, DB credentials, and provider keys centralized and auditable.
- Consequences:
  - Docker builds intended for production must use `docker buildx build --platform linux/amd64` before pushing to ECR; ARM-native images that work on Apple Silicon fail in App Runner otherwise.
  - Deployment workflow: `docker login` to ECR, build & push image, update App Runner service to the new tag (future CI/CD will automate this).
  - Runtime environment variables are no longer read from repo-local `.env` in production; they must be added/updated in Secrets Manager.

## 2025-12-25 — Email verification tokens are single-use + token-versioned sessions
- Decision: Persist hashed verification token IDs (`email_verification_tokens`) so email links are single-use, and embed a `token_version` claim into access tokens so user sessions can be revoked by bumping the column (e.g., on password change or admin deletion).
- Rationale: Prevents recycled verification links from working after resends or account recreation, and ensures users are logged out promptly when credentials change.
- Consequences:
  - `/auth/verify` now errors after a link is used once; resending a verification email invalidates any prior link.
  - Access tokens created before a `token_version` bump are rejected (`401`), forcing re-auth even if a refresh token remains.
  - Change-password flow increments `token_version` in addition to revoking refresh tokens.

---

## 2025-12-18 — User settings persisted on users table
- Decision: Persist user preference `auto_refresh_seconds` on the `users` table and expose via `/users/me/settings`.
- Rationale: Keeps a single-user settings surface area small and avoids separate settings tables prematurely.
- Consequences:
  - Future expansion may warrant a dedicated settings table/schema if preferences grow.

---

## 2025-12-19 — Tailwind v4 dark mode uses class-based variant
- Decision: Configure Tailwind v4 `dark:` to follow the `.dark` class (not `prefers-color-scheme`) using `@custom-variant` in `frontend-web/src/index.css`.
- Rationale: Enables app-controlled theme switching (dark/light/system) without relying on OS theme.
- Consequences:
  - Theme changes apply immediately when toggling `.dark` on `<html>`.

---

## 2025-12-19 — Phase 4 refactor approach: extract modules + shared UI class helpers
- Decision: Refactor large frontend pages by extracting pure helpers and presentational components into colocated modules (e.g. `frontend-web/src/pages/jobs/*`). Introduce a tiny shared `frontend-web/src/styles/ui.ts` for repeated Tailwind class strings.
- Rationale: Shrinks large files, reduces duplication, and keeps behavior stable by leaving orchestration/state in the original page while moving UI chunks out.
- Consequences:
  - New modules are intentionally “dumb”/presentational; page owns state.
  - Styling changes are consolidated via shared class constants (still Tailwind; no new deps).

---

## 2025-12-19 — Backend job ownership helpers centralized
- Decision: Centralize repeated job ownership lookup and tag normalization/tag replacement helpers in `backend/app/services/jobs.py` and import them in jobs-related routers.
- Rationale: Removes duplication across routers and keeps route modules thinner and more consistent.
- Consequences:
  - Routers share a single `get_job_for_user(...)` behavior (404 message/shape remains consistent).

---

## 2025-12-19 — Backend auth + documents route helpers extracted into services
- Decision: Extract refresh token/cookie helpers into `backend/app/services/refresh_tokens.py` and document presign validation/replacement helpers into `backend/app/services/documents.py`.
- Rationale: Keep route modules focused on HTTP orchestration and reuse shared policy/validation logic.
- Consequences:
  - Auth routes call shared functions for refresh rotation and cookie handling (behavior unchanged).
  - Document presign endpoint uses shared validation/limits and single-doc replacement logic (behavior unchanged).

---

## 2025-12-19 — Backend standard error response envelope
- Decision: Add global exception handlers in `backend/app/main.py` so API errors follow the standard `{error, message, details?}` contract documented in `docs/api/error-format.md`.
- Rationale: Makes frontend error handling consistent and enables stable tests against API error responses.
- Consequences:
  - `HTTPException` and request validation errors are consistently shaped.
  - Tests can assert stable error codes (e.g., `NOT_FOUND`, `UNAUTHORIZED`, `VALIDATION_ERROR`).

---

## 2025-12-19 — Testing strategy: mock API boundaries, avoid UI snapshots
- Decision: Frontend tests use Vitest + React Testing Library and mock `frontend-web/src/api.ts` rather than snapshot testing or deep component implementation assertions.
- Rationale: Keeps tests resilient while still validating critical user flows and error handling.
- Consequences:
  - Most frontend tests assert on visible text, routing, and API call arguments.
  - Backend tests use pytest with an in-memory SQLite harness for fast, isolated runs.