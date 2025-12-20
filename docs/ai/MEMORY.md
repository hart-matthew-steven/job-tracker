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
  - Provider default is **SES via boto3**; SMTP remains optional fallback.
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
- Dev exposure + document verification pipeline not yet implemented:
  - Backend behind ngrok (dev)
  - ClamAV scanning Lambda to mark uploaded docs verified/infected
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

## Utilities
- Dev DB reset + S3 cleanup script: `temp_scripts/reset_dev_db.py`
  - Requires `ENV=dev`
  - Interactive confirmation unless `--yes`
  - Writes a timestamped log to `logs/reset_dev_db_*.log`
