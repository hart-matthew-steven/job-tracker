# docs/ai/MAP.md
# Repo Map (High-level)

This file is a quick index of "where things live" to reduce repeated re-explaining.
Update it whenever key entry points or folder structure changes.

## Frontend (`frontend-web/`)
- Entry: `frontend-web/src/main.tsx`
- App routes: `frontend-web/src/App.tsx`
- API client: `frontend-web/src/api.ts`
- Routes constants: `frontend-web/src/routes/paths.ts`
- Pages:
  - Auth: `frontend-web/src/pages/auth/*`
  - Core: `frontend-web/src/pages/DashboardPage.tsx`, `frontend-web/src/pages/JobsPage.tsx`
  - Account: `frontend-web/src/pages/account/index.tsx`
- UI building blocks:
  - Layout shell: `frontend-web/src/components/layout/AppShell.tsx`
  - Toasts: `frontend-web/src/components/ui/ToastProvider.tsx`
  - Modal: `frontend-web/src/components/ui/Modal.tsx`
- Jobs page submodules: `frontend-web/src/pages/jobs/*`
- Frontend tests: `frontend-web/src/**/*.test.tsx` (Vitest)

## Backend (`backend/`)
- Entry: `backend/app/main.py` (expected)
- Routes: `backend/app/routes/` (expected)
- Services: `backend/app/services/` (expected)
- Core (auth/config/db): `backend/app/core/` (expected)
- Models: `backend/app/models/` (expected)
- Schemas: `backend/app/schemas/` (expected)
- Backend tests: `backend/tests/` (pytest)

## Architecture Docs
- Overview: `docs/architecture/overview.md`
- Data flow: `docs/architecture/data-flow.md`
- Security: `docs/architecture/security.md`

## AI Docs
- Memory: `docs/ai/MEMORY.md`
- Decisions: `docs/ai/DECISIONS.md`
- Repo map: `docs/ai/MAP.md`

## Logs (ignored by default in Git)
- AI outputs: `logs/ai/`
- Script outputs: `logs/scripts/`