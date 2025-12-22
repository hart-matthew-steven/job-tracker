# docs/ai/MEMORY.md
# Project Memory (Authoritative)

Purpose: durable, repo-managed project state so future sessions can resume reliably.
Keep it concise, factual, and employer-facing.

## Current Implementation Status
### Frontend (`frontend-web/`)
- App shell with responsive nav and account menu.
- Auth pages: Login / Register / Verify (verify is auto-only via email link).
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
- Documents:
  - Presigned S3 upload flow implemented (presign → upload to S3 → confirm).

## What Is Working
- Registration → email verification link → verification → login.
- Logout + auth navigation guards.
- Profile fetch.
- Change password (shows validation errors; on success logs out and routes to login).
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
- Document malware scanning fully implemented:
  - **AWS GuardDuty Malware Protection for S3** is the production scan engine.
  - EventBridge triggers a Lambda forwarder (`lambda/guardduty_scan_forwarder/`).
  - Lambda extracts `document_id` from S3 key and calls backend internal callback.
  - Verdict source of truth is the S3 object tag `GuardDutyMalwareScanStatus`; if the EventBridge event does not include tags, the Lambda calls S3 `GetObjectTagging` to read the verdict.
  - Backend updates DB `scan_status` (PENDING → CLEAN/INFECTED/ERROR) and blocks downloads unless CLEAN.
  - Frontend polls for status updates and displays scan state.
  - Backend can still be exposed via ngrok for local dev/testing.
- Production AWS deployment hardening is explicitly deferred until requested.

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

## Utilities
- Dev DB reset + S3 cleanup script: `temp_scripts/reset_dev_db.py`
  - Requires `ENV=dev`
  - Interactive confirmation unless `--yes`
  - Writes a timestamped log to `logs/reset_dev_db_*.log`
