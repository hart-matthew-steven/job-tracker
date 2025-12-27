# docs/ai/CONTEXT.md
# Job Tracker — Project Context

## Overview
Job Tracker is a personal job application tracking system with:
- A web frontend for managing applications, notes, and documents
- A Python API backend for auth, persistence, and document workflows
- Enforced password policy + rotation (minimum length, complexity, expiration warnings)

Primary goals:
- Track job applications + statuses
- Attach notes and documents per application
- Provide a safe upload flow (presign upload → confirm) and basic operational guardrails

## Tech Stack
### Frontend (`frontend-web/`)
- React + Vite (TypeScript)
- Tailwind CSS
- React Router
- Central API client in `frontend-web/src/api.ts`
- Tests: Vitest + React Testing Library
- Shared password policy helper in `src/lib/passwordPolicy.ts`
- Password requirements UI (`src/components/forms/PasswordRequirements.tsx`) blocks weak passwords on Register/Change Password

### Backend (`backend/`)
- FastAPI
- SQLAlchemy ORM + Alembic migrations
- Postgres
- JWT access tokens (Bearer)
- Refresh tokens stored in DB, delivered via HttpOnly cookie
- AWS SDK: `boto3` (used for SES and S3-related workflows)
- Tests: pytest
- Strong password policy enforced when setting passwords via `app/core/password_policy.py`
- `users.password_changed_at` tracks rotation; login responses include `must_change_password`
- Database access split between least-privilege runtime (`DB_APP_USER`) and migrations (`DB_MIGRATOR_USER`) credentials, each with its own connection URL.
- Production hosting: AWS App Runner pulling images from ECR, fronted by `https://api.jobapptracker.dev`; runtime secrets come from AWS Secrets Manager env injects.

## AWS / External Services (current)
- **Email**: provider-selectable for verification emails:
  - `resend` (default)
  - `ses`
  - `gmail` (SMTP)
  - legacy alias: `smtp` → `gmail`
- **S3**: job document upload flow via presigned URLs (see `/jobs/{job_id}/documents/*`)
- **GuardDuty Malware Protection for S3**: AWS-managed malware scanning for uploaded documents. EventBridge triggers a Lambda forwarder, which updates the backend document `scan_status`. The GuardDuty verdict is sourced from the S3 object tag `GuardDutyMalwareScanStatus` (Lambda falls back to S3 `GetObjectTagging` if the event payload does not include tags). GuardDuty callbacks are feature-gated via `GUARD_DUTY_ENABLED` so local Docker runs can noop safely.
- **App Runner**: hosts the backend container, pulls from ECR with `linux/amd64` images, injects env vars from Secrets Manager, handles health checks routed through `/health`.

## Intended Future Direction (high-level)
- iOS app (separate client, likely `frontend-ios/` when introduced)
- AWS hardening and production infrastructure (explicitly staged); next step is CI/CD to build & deploy backend (App Runner) and later frontend automatically on merge to `main`.
- AI assistant features (resume/job-description tailoring, cover/thank-you letters with automatic S3 upload to a job record).
- Multi-factor authentication, passkey login, eventual biometric (Face ID) support on iOS.
- Continued refactors: improve maintainability, reduce duplication, keep tests comprehensive

## Key Flows
### Auth + Email verification
- Register → verification email sent → user clicks frontend `/verify?token=...` → frontend calls backend `/auth/verify` → then login allowed.
- Register/change/reset password enforce password policy (length, mixed case, number, special, denylist, no email/name). Expired passwords still log in but responses set `must_change_password` so UI can redirect to Change Password.

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


