# .cursor/rules/20-backend.md
# Backend Rules (Python API)

## Structure & Boundaries
- Routes/controllers stay thin: validation + wiring.
- Business logic belongs in services.
- Schemas define request/response contracts.
- Models define persistence.
- Prefer explicit, readable control flow.

## Refactor Preferences
- Remove duplication.
- Standardize error handling.
- Preserve API shapes unless explicitly requested.

## Reliability
- Prefer “boring and correct” over “clever and fragile.”
- If auth/session, persistence, or file-handling behavior might change, flag it early.

## Security
- Treat all external input as untrusted.
- Keep upload/scan flow intact (no bypasses).
- Never log sensitive payloads or secrets.

## Documentation
- Add docstrings to public functions and service entry points.
- Comments explain WHY, not WHAT.