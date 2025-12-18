# docs/ai/MEMORY.md
# Project Memory (Authoritative)

Purpose: durable, repo-managed project state so future sessions can resume reliably.
Keep it concise, factual, and employer-facing.

## Current Implementation Status
### Frontend (`frontend-web/`)
- Dark, neutral app shell with responsive nav and account menu.
- Auth pages: Login / Register / Verify (verify is auto-only via email link).
- Jobs page: search + sort + load-more UI; “Last updated” timestamp; auto-refresh (controlled by user setting).
- Profile + Change Password wired to backend APIs.
- Settings page wired to backend (no `localStorage` persistence).

### Backend (`backend/`)
- FastAPI + SQLAlchemy + Alembic migrations.
- Auth model:
  - JWT access token via `Authorization: Bearer ...`
  - Refresh tokens stored in DB, set as HttpOnly cookie
  - Email verification required before login
- Users:
  - `/users/me` returns user profile (includes `name`)
  - `/users/me/change-password` validates current password, updates hash, revokes refresh tokens
  - Settings stored on user (`auto_refresh_seconds`) with `/users/me/settings` GET/PUT
- Email delivery:
  - Provider default is **SES via boto3**; SMTP remains optional fallback.
- Documents:
  - Presigned S3 upload flow implemented (presign → upload to S3 → confirm).

## What Is Working
- Registration → email verification link → verification → login.
- Logout + auth navigation guards.
- Profile fetch.
- Change password (shows validation errors; on success logs out and routes to login).
- DB-backed settings (auto refresh frequency).
- Job listing + detail view (notes + documents panels) with auth.

## Partially Implemented / Deferred
- Phase 2 reset script (truncate tables + S3 cleanup) is not implemented yet.
- TypeScript migration (Phase 3) not started.
- Backend/API error format standardization not completed.
- Production AWS deployment hardening is explicitly deferred until requested.

## Known Issues / Notes
- SES deliverability: verification emails may land in spam depending on sender identity/domain posture.
- Some frontend screens are large (notably `frontend-web/src/App.jsx`) and should be split during refactor phase.

## Actively Working On (RIGHT NOW)
- Preparing Phase 2: dev reset script with guardrails and S3 cleanup.
