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
- TypeScript migration (Phase 3) not started.
- Backend/API error format standardization not completed.
- Production AWS deployment hardening is explicitly deferred until requested.

## Known Issues / Notes
- SES deliverability: verification emails may land in spam depending on sender identity/domain posture.
- Some frontend screens are large (notably `frontend-web/src/App.tsx`) and should be split during refactor phase.

## Recent Changes
- Extracted account pages from `frontend-web/src/App.tsx` into `frontend-web/src/pages/account/` (no behavior change).
- Extracted auth shell + redirect guard from `frontend-web/src/App.tsx` into `frontend-web/src/pages/auth/` (no behavior change).

## Actively Working On (RIGHT NOW)
- Next: migrate `frontend-web/` to TypeScript (incremental, mechanical; no behavior changes).

## TypeScript Migration Notes
- TS setup is being introduced incrementally to avoid breaking builds:
  - `frontend-web/tsconfig.json` added
  - `npm run typecheck` added
  - Began Phase 3.2 conversions: `frontend-web/src/routes/paths.js` → `frontend-web/src/routes/paths.ts`
  - Converted API client: `frontend-web/src/api.js` → `frontend-web/src/api.ts` (+ `frontend-web/src/types/api.ts`)
  - ESLint updated to parse TypeScript (`@typescript-eslint/parser` + plugin) and only apply React Refresh rules to JSX/TSX files
  - ESLint TS config: disabled `no-undef` for TS/TSX (it flags TS types like `RequestInit`)
  - Converted hooks: `frontend-web/src/hooks/useSettings.ts`, `frontend-web/src/hooks/useCurrentUser.ts`
  - Converted component: `frontend-web/src/components/jobs/JobCard.jsx` → `.tsx`
  - Converted components: `frontend-web/src/components/jobs/JobDetailsCard.jsx` → `.tsx`, `frontend-web/src/components/jobs/JobsList.jsx` → `.tsx`, `frontend-web/src/components/jobs/NotesCard.jsx` → `.tsx`
  - Converted documents components: `frontend-web/src/components/documents/DocRow.jsx` → `.tsx`, `frontend-web/src/components/documents/DocumentSection.jsx` → `.tsx`, `frontend-web/src/components/documents/DocumentsPanel.jsx` → `.tsx`
  - Fixed a TSX parse issue in `DocumentSection.tsx` (duplicate component declaration removed)
  - Fixed TypeScript typecheck issues in documents components (`jobId` null guards; `activeDocId` sentinel typing)
  - Adjusted `PresignUploadIn.content_type` type to allow `null` (matches payload)
  - Fixed `PresignUploadIn` shape to include `doc_type`/`size_bytes` (matches documents presign payload)
  - Converted auth provider to TSX with a `.jsx` shim: `src/auth/AuthProvider.tsx` + `src/auth/AuthProvider.jsx` re-export
  - Converted auth guard to TSX with a `.jsx` shim: `src/auth/RequireAuth.tsx` + `src/auth/RequireAuth.jsx` re-export
  - Converted app shell to TSX with a `.jsx` shim: `src/components/layout/AppShell.tsx` + `src/components/layout/AppShell.jsx` re-export
  - Converted auth redirect guard to TSX with a `.jsx` shim: `src/pages/auth/RedirectIfAuthed.tsx` + `src/pages/auth/RedirectIfAuthed.jsx` re-export
  - Converted auth pages: `AuthShellLayout`, `LoginPage`, `RegisterPage`, `VerifyEmailPage` to TSX with `.jsx` shims
  - Converted entry + account pages module: `src/main.tsx`, `src/pages/account/index.tsx`
  - Removed temporary `any` casts from `JobsPage.tsx` by typing the form state + callbacks properly
  - Removed remaining `.jsx` shims and switched `index.html` entry to `/src/main.tsx`
  - TS hardened: `frontend-web/src/` now contains no JS/JSX; `frontend-web/tsconfig.json` now has `allowJs=false`

## Recent Changes
- Lint fixes (frontend): adjusted auth provider memoization/exports and removed a try/catch JSX return; fixed unused-var warning in documents section.
- Lint baseline tightened: removed unused eslint-disable in `DashboardPage.jsx`; removed `return` from `finally` in `JobsPage.jsx`.
- Removed unused ESLint disable directives from TS migration `.jsx` shim re-export files.

## Utilities
- Dev DB reset + S3 cleanup script: `temp_scripts/reset_dev_db.py`
  - Requires `ENV=dev`
  - Interactive confirmation unless `--yes`
  - Writes a timestamped log to `logs/reset_dev_db_*.log`
