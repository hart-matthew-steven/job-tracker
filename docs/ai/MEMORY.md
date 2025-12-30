# docs/ai/MEMORY.md
# Project Memory (Authoritative)

Purpose: durable, repo-managed project state so future sessions can resume reliably.
Keep it concise, factual, and employer-facing.

## Current Implementation Status
### Frontend (`frontend-web/`)
- App shell with responsive nav and account menu.
- Auth pages: Login / Register / Verify (verify is auto-only via email link).
- Register + Change Password now share a password policy helper and inline `PasswordRequirements` list to block weak passwords before submission; backend error violations render in the UI.
- Jobs page:
  - Server-side search + filters (q, tags, multi-select statuses)
  - Saved views UI
  - Timeline + interviews panels
  - Auto-refresh (controlled by user setting)
  - Defaults: applies account default sort/view on first load; “Use defaults” button to re-apply
- Profile + Change Password wired to backend APIs.
- Settings page wired to backend:
  - Auto refresh frequency
  - Jobs default sort/view
  - Theme (dark/light/system) applied app-wide (Tailwind `dark` class)
  - Data retention (UI-only): jobs older than N days are hidden in Jobs + Dashboard (data stays in DB)

### Backend (`backend/`)
- FastAPI + SQLAlchemy + Alembic migrations.
- Auth model:
  - JWT access token via `Authorization: Bearer ...`
  - Refresh tokens stored in DB, set as HttpOnly cookie
  - Email verification required before login
- Users:
  - `/users/me` returns user profile (includes `name`)
  - `/users/me/change-password` validates current password, updates hash, revokes refresh tokens
- Settings stored on user with `/users/me/settings` GET/PUT:
  - `auto_refresh_seconds`, `theme`, `default_jobs_sort`, `default_jobs_view`, `data_retention_days`
- Email delivery:
  - Provider default is **Resend** (when `EMAIL_PROVIDER` is unset).
  - Supported providers: `resend` (default), `ses`, `gmail` (SMTP); legacy alias `smtp` → `gmail`.
- Email verification:
  - Tokens are JWTs with single-use IDs stored in `email_verification_tokens`; clicking a link consumes the record so resends invalidate prior links automatically.
- Password policy:
  - Configurable via `PASSWORD_MIN_LENGTH` (default 14) and `PASSWORD_MAX_AGE_DAYS` (default 90).
  - `app/core/password_policy.py` enforces requirements (length, upper/lowercase, number, special char, denylist, no email/name).
  - `users.password_changed_at` tracks rotations; login/refresh + `/users/me` responses include `must_change_password` so the frontend can gate access.
- Database access:
  - Runtime API connects with `DB_APP_USER` / `DB_APP_PASSWORD` (CRUD-only).
  - Alembic migrations run with `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD` (DDL).
  - Config exposes both URLs (`database_url`, `migrations_database_url`), keeping least privilege enforced in prod and dev.
- Optional integrations:
  - `EMAIL_ENABLED` and `GUARD_DUTY_ENABLED` gate external dependencies; when disabled (default in Docker), email send + GuardDuty callbacks noop safely.
- Deployment:
  - Production backend runs on AWS App Runner behind `https://api.jobapptracker.dev`, pulling ECR images built with `docker buildx --platform linux/amd64` and loading secrets from AWS Secrets Manager.
  - GitHub Actions handle production deploys: `backend-deploy.yml` builds/pushes images and calls `scripts/deploy_apprunner.py`; `frontend-deploy.yml` builds the Vite SPA, uploads a versioned release to S3, promotes it, updates metadata, invalidates CloudFront, and runs health checks via `scripts/deploy_frontend.py`.
- Documents:
  - Presigned S3 upload flow implemented (presign → upload to S3 → confirm).
 - Auth tokens:
   - Access tokens include a `token_version`, letting the backend invalidate sessions by incrementing the column (e.g., on password change). Refresh tokens are still revoked server-side.

## What Is Working
- Registration → email verification link → verification → login.
- Logout + auth navigation guards.
- Profile fetch.
- Change password (shows validation errors; on success logs out and routes to login). Enforces the same password policy as registration; expired passwords trigger the change-password redirect.
- DB-backed settings (auto refresh + jobs defaults + theme + data retention preference).
- Job listing + detail view (notes + documents panels) with auth.
- Tags end-to-end (stored on jobs; filterable in UI; persisted in saved views).
- Job activity timeline (notes/documents/status updates).
- Job interviews CRUD in UI + backend.

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
 - Email delivery refactor:
  - Default provider is `resend` with Resend Python SDK.
  - Env vars: `FROM_EMAIL` (ses/resend only), `RESEND_API_KEY`, `AWS_REGION` for SES.
  - Backend env var example is generated at `backend/.env.example` via `tools/generate_env_example.py`.
- Hosting upgrade:
  - Backend Dockerfile + README updated for App Runner (ECR build/push commands, `--platform linux/amd64` requirement, secrets from AWS Secrets Manager, health checks hitting `/health`).
- CI/CD automation:
  - `backend-deploy.yml` + `scripts/deploy_apprunner.py` build/push the API image, update App Runner, wait for health, and roll back on failure.
  - `frontend-deploy.yml` + `scripts/deploy_frontend.py` version frontend builds in S3, promote releases, invalidate CloudFront, and keep rollback metadata in `_releases/current.json`.
- GuardDuty + email gating:
  - Introduced `EMAIL_ENABLED` / `GUARD_DUTY_ENABLED` feature flags so local Docker can run without external services; added noop handlers + test coverage.
- Password policy + rotation:
  - Added password policy helper + env vars, enforced at registration/change flows.
  - Alembic migration backfilled `password_changed_at`; auth responses expose `must_change_password`.
  - Frontend mirrors the rules client-side and blocks weak passwords with a shared helper + requirements UI.

## Utilities
- Dev DB reset + S3 cleanup script: `temp_scripts/reset_dev_db.py`
  - Requires `ENV=dev`
  - Interactive confirmation unless `--yes`
  - Writes a timestamped log to `logs/reset_dev_db_*.log`
