# docs/ai/MAP.md
# Repo Map (High-level)

This file is a quick index of "where things live" to reduce repeated re-explaining.
Update it whenever key entry points or folder structure changes.

## Frontend (`frontend-web/`)
- Entry: `frontend-web/src/main.jsx` (expected)
- App shell: `frontend-web/src/App.jsx` (expected)
- API client: (add path once confirmed)
- Pages/Routes: (add path once confirmed)

## Backend (`backend/`)
- Entry: `backend/app/main.py` (expected)
- Routes: `backend/app/routes/` (expected)
- Services: `backend/app/services/` (expected)
- Core (auth/config/db): `backend/app/core/` (expected)
- Models: `backend/app/models/` (expected)
- Schemas: `backend/app/schemas/` (expected)

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