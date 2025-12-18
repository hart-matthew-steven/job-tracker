# docs/ai/CONTEXT.md
# Job Tracker — Project Context

## Overview
Job Tracker is a personal job application tracking system with:
- A web frontend for managing applications, notes, and documents
- A Python API backend for auth, persistence, and document workflows

Primary goals:
- Track job applications + statuses
- Attach notes and documents per application
- Provide a safe upload flow (presign upload → confirm) and basic operational guardrails

## Tech Stack
### Frontend (`frontend-web/`)
- React + Vite (JavaScript)
- Tailwind CSS
- React Router
- Central API client in `frontend-web/src/api.js`

### Backend (`backend/`)
- FastAPI
- SQLAlchemy ORM + Alembic migrations
- Postgres
- JWT access tokens (Bearer)
- Refresh tokens stored in DB, delivered via HttpOnly cookie
- AWS SDK: `boto3` (used for SES and S3-related workflows)

## AWS / External Services (current)
- **SES**: email verification delivery via `boto3` (provider default)
- **S3**: job document upload flow via presigned URLs (see `/jobs/{job_id}/documents/*`)

## Intended Future Direction (high-level)
- iOS app (separate client, likely `frontend-ios/` when introduced)
- AWS hardening and production infrastructure (explicitly staged; do not start ngrok/Lambda/scan pipeline work unless requested)
- Continued refactors: improve maintainability, reduce duplication, add typed client models (TypeScript migration is planned)

## Key Flows
### Auth + Email verification
- Register → verification email sent → user clicks frontend `/verify?token=...` → frontend calls backend `/auth/verify` → then login allowed.

### Job documents (S3)
- Backend issues presigned upload URL → client uploads directly to S3 → client confirms upload → backend tracks document metadata + status.

## Where to Look
- Frontend entry: `frontend-web/src/main.tsx` → `frontend-web/src/App.tsx`
- Backend entry: `backend/app/main.py`
- Backend routes: `backend/app/routes/`
- DB models: `backend/app/models/`
- Schemas: `backend/app/schemas/`
- Migrations: `backend/alembic/versions/`
- Durable AI context: `docs/ai/MEMORY.md` (authoritative) + `docs/ai/TASKS.md`


