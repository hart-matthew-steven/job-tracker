# docs/ai/TASKS.md
# Tasks

## In Progress
- Phase 7: CI quality gate (block merges when checks fail):
  - GitHub Actions workflows added
  - Branch protection (required checks) needs to be enabled in GitHub UI

## Next
- (none)

## Later
- Phase 8: Dev exposure + upload verification pipeline (after CI is in place):
  - Expose backend behind ngrok for dev/testing (documented + repeatable)
  - Implement ClamAV scanning pipeline:
    - S3 upload triggers Lambda (or equivalent) to scan object with ClamAV
    - Update backend to mark document `verified` vs `infected` (finish the verification step)
    - Ensure UI transitions from `pending/scanning` → final status
- Phase 9: Production architecture planning (deferred until explicitly requested): deployment, secrets, SES domain identity, S3 policies, scanning pipeline

## Completed
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


