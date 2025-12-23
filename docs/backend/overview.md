# Backend Overview

This document describes the backend structure and conventions at a high level.

---

## Stack

- Python API (FastAPI-style architecture)
- Persistence: PostgreSQL + SQLAlchemy
- Background processing: AWS-managed (EventBridge, Lambda)
- File scanning: AWS GuardDuty Malware Protection for S3

### Database connectivity

- Shared settings: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSLMODE` (always set to `require` so TLS is enforced).
- Runtime traffic uses `DB_APP_USER` / `DB_APP_PASSWORD`. This account is limited to data reads/writes and intentionally blocked from `CREATE TABLE` / `ALTER TABLE`.
- Schema changes run through Alembic using `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD`, the only credentials with DDL privileges.
- Two discrete URLs exist in config: `database_url` (app) and `migrations_database_url` (Alembic). This protects production data by enforcing least privilege and keeps migrations auditable.
- Legacy `DB_USER` / `DB_PASSWORD` configuration has been removed; always supply both credential sets explicitly.

---

## Responsibilities

- Owns business logic and persistence
- Provides a clean API contract to the frontend
- Handles uploads securely (scan-before-accept)
- Coordinates async jobs (scan, processing, analytics if added)

---

## Structure (fill in once confirmed)

Typical layout:
- `backend/app/main.py` — app entry point
- `backend/app/routes/` — HTTP routes
- `backend/app/services/` — business logic
- `backend/app/models/` — persistence models
- `backend/app/schemas/` — IO contracts
- `backend/app/core/` — config/auth/shared utilities

---

## Conventions

- Routes stay thin; services own logic
- Consistent error format
- Preserve API shapes during refactors unless intentionally versioned
- Treat uploads as hostile until scanned

---

## Email delivery (configuration)

The backend sends verification emails using the configured provider.

- **`EMAIL_PROVIDER`**: defaults to `resend` when unset.
  - Supported: `resend` (default), `ses`, `gmail`
  - Legacy alias: `smtp` is treated as `gmail`
- **`FROM_EMAIL`**: used only for `resend` and `ses` (do not use for `gmail`)
- **`RESEND_API_KEY`**: required when using `resend`
- **`AWS_REGION`**: used for AWS clients (including SES)

See `backend/.env.example` for the full list of backend variable names.

---

## Updating this document

Update when:
- folder structure changes
- auth/session model changes
- persistence approach changes
- background job architecture changes