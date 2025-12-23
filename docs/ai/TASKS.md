# docs/ai/TASKS.md
# Tasks

## In Progress
- Phase 7: CI quality gate (block merges when checks fail):
  - GitHub Actions workflows added
  - Branch protection (required checks) needs to be enabled in GitHub UI

- Email delivery: Resend provider + env var contract:
  - Default email provider is `resend`
  - Supported: `resend`, `ses`, `gmail` (legacy alias: `smtp` → `gmail`)
  - Backend env var example generated at `backend/.env.example`

## Next
- (none)

## Later
- Production deployment:
  - Host backend behind stable AWS ingress (ALB/API Gateway)
  - Replace ngrok with production endpoint for Lambda → backend callbacks
  - Enable branch protection in GitHub (require CI checks to pass)
  - Configure stable domain for frontend
  - Harden secrets management (AWS Secrets Manager)

## Completed
- **Phase 8: Malware scanning pipeline** (GuardDuty Malware Protection for S3):
  - Migrated from ClamAV-based scanning to AWS GuardDuty for production reliability
  - Removed: ClamAV Lambda code, SQS triggers, EFS definitions, quarantine logic
  - Added: `lambda/guardduty_scan_forwarder/` (EventBridge → Lambda → backend callback)
  - Backend/frontend unchanged (same DB fields, internal callback API, download gating)
  - Architecture docs updated (`docs/architecture/security.md`, `docs/architecture/data-flow.md`)
- **Email delivery refactor**:
  - Default provider: `resend` (with fallback to `ses`, `gmail`/`smtp`)
  - Environment variable contract: `EMAIL_PROVIDER`, `FROM_EMAIL`, `RESEND_API_KEY`, `AWS_REGION`
  - Backend `.env.example` generated and documented
- Strong password policy + rotation:
  - Added `PASSWORD_MIN_LENGTH` / `PASSWORD_MAX_AGE_DAYS`, `password_changed_at`, and `must_change_password` responses.
  - Backend enforces requirements (uppercase/lowercase/number/special/denylist/no email/name) when registering/changing passwords.
  - Frontend mirrors the helper/UI requirements and blocks navigation until expired passwords are updated.
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
- Refactor frontend: split `frontend-web/src/App.tsx` (extract pages/components/hooks), add `src/routes/paths.ts`, and group job components under `src/components/jobs/`.
- Consolidate backend user/settings responses (use dedicated settings schema for `/users/me/settings`)
- Phase 2: dev reset script implemented: `temp_scripts/reset_dev_db.py` (guardrails, S3 cleanup, logs, `--yes`)


