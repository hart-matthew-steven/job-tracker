# docs/ai/TASKS.md
# Tasks

## In Progress
- (none)

## Next
- Phase 3: migrate `frontend-web/` to TypeScript (incremental, mechanical; no behavior changes)
  - Phase 3.1: TS setup (deps + tsconfig + typecheck script)
  - Phase 3.1.1: Fix existing lint blockers (auth/documents/pages) so the baseline is clean
  - Phase 3.2: Convert lowest-risk leaf files first (routes/constants/hooks/api)
    - Converted `src/routes/paths.js` → `src/routes/paths.ts`
    - Converted `src/api.js` → `src/api.ts` (added `src/types/api.ts`)
    - Updated ESLint to parse TS/TSX and avoid React Refresh rules on non-JSX files (also disabled `no-undef` for TS types)
    - Converted hooks: `src/hooks/useSettings.ts`, `src/hooks/useCurrentUser.ts`
    - Converted component: `src/components/jobs/JobCard.jsx` → `.tsx`
    - Converted components: `src/components/jobs/JobDetailsCard.jsx` → `.tsx`, `src/components/jobs/JobsList.jsx` → `.tsx`, `src/components/jobs/NotesCard.jsx` → `.tsx`
    - Converted documents components: `src/components/documents/DocRow.jsx` → `.tsx`, `src/components/documents/DocumentSection.jsx` → `.tsx`, `src/components/documents/DocumentsPanel.jsx` → `.tsx`
    - Converted auth: `src/auth/AuthProvider.jsx` → `.tsx` (kept `.jsx` shim to avoid import churn)
    - Converted auth: `src/auth/RequireAuth.jsx` → `.tsx` (kept `.jsx` shim to avoid import churn)
    - Converted layout: `src/components/layout/AppShell.jsx` → `.tsx` (kept `.jsx` shim to avoid import churn)
    - Converted auth pages: `AuthShellLayout`, `LoginPage`, `RegisterPage`, `VerifyEmailPage` to TSX (kept shims)
  - Phase 3.3: Convert components, then pages
    - Converted `App`, `main`, and pages to TSX; removed all `.jsx` shims; set `allowJs=false`
- Feature buildout (personal-use focus):
  - Statuses + pipeline
  - Saved views
  - Search + filters
  - Tags
  - Timeline (job activity)
  - Interview tracking
  - Offer tracking
- Settings expansion:
  - Defaults
  - Auto refresh (already exists; extend as needed)
  - Appearance
  - Data retention
- Tighten email deliverability for SES (SPF/DKIM/DMARC) when moving toward public launch

## Later
- Phase 4: refactors (frontend + backend duplication reduction)
- Standardize API error shape (align backend responses with `docs/api/error-format.md`)
- Production architecture planning (deferred until explicitly requested): deployment, secrets, SES domain identity, S3 policies, scanning pipeline

## Completed
- Refactor frontend: split `frontend-web/src/App.tsx` (extract pages/components/hooks), add `src/routes/paths.ts`, and group job components under `src/components/jobs/`.
- Consolidate backend user/settings responses (use dedicated settings schema for `/users/me/settings`)
- Phase 2: dev reset script implemented: `temp_scripts/reset_dev_db.py` (guardrails, S3 cleanup, logs, `--yes`)


