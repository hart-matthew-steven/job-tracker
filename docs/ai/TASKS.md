# docs/ai/TASKS.md
# Tasks

## In Progress
- Phase 2: `temp_scripts/` reset + S3 cleanup script (dev-only guardrails, logs, `--yes`)

## Next
- Tighten email deliverability for SES (SPF/DKIM/DMARC) when moving toward public launch
- Refactor frontend: split `frontend-web/src/App.jsx` (extract pages/components/hooks) while preserving behavior
- Consolidate backend user/settings responses (consider dedicated settings schema vs reusing user schema)

## Later
- Phase 3: incremental TypeScript migration for `frontend-web/`
- Phase 4: refactors (frontend + backend duplication reduction)
- Standardize API error shape (align backend responses with `docs/api/error-format.md`)
- Production architecture planning (deferred until explicitly requested): deployment, secrets, SES domain identity, S3 policies, scanning pipeline


