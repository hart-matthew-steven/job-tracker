# Backend Overview

This document describes the backend structure and conventions at a high level.

---

## Stack

- Python API (FastAPI-style architecture)
- Persistence: PostgreSQL + SQLAlchemy
- Background processing: AWS-managed (EventBridge, Lambda)
- File scanning: AWS GuardDuty Malware Protection for S3
- Authentication: JWT access tokens + HttpOnly refresh cookies, Argon2 password hashing, password rotation

### Database connectivity

- Shared settings: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSLMODE` (always set to `require` so TLS is enforced).
- Runtime traffic uses `DB_APP_USER` / `DB_APP_PASSWORD`. This account is limited to data reads/writes and intentionally blocked from `CREATE TABLE` / `ALTER TABLE`.
- Schema changes run through Alembic using `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD`, the only credentials with DDL privileges.
- Two discrete URLs exist in config: `database_url` (app) and `migrations_database_url` (Alembic). This protects production data by enforcing least privilege and keeps migrations auditable.
- Legacy `DB_USER` / `DB_PASSWORD` configuration has been removed; always supply both credential sets explicitly.

### Hosting & deployment

- Production backend runs on **AWS App Runner** behind `https://api.jobapptracker.dev`.
- Environment variables (JWT secret, database credentials, email/GuardDuty toggles, etc.) are sourced from **AWS Secrets Manager** and injected into the App Runner service—no secrets live in the repo.
- Container images are built locally or via CI and pushed to Amazon ECR. Always use `docker buildx build --platform linux/amd64` so the artifact matches App Runner’s runtime; images that run on Apple Silicon without the flag will fail to boot in App Runner.
- After pushing `ACCOUNT_ID.dkr.ecr.<region>.amazonaws.com/<repo_name>:<tag>`, update the App Runner service to pull the new tag; App Runner handles rolling deployment and health checks.

### Password policy

- Configurable via `PASSWORD_MIN_LENGTH` (default 14) and `PASSWORD_MAX_AGE_DAYS` (default 90). Strength checks apply whenever passwords are set or changed; login never rejects existing weak passwords.
- A dedicated `password_changed_at` timestamp on `users` tracks the last rotation. Auth responses (login/refresh/`GET /users/me`) include `must_change_password` when the age limit is exceeded so the frontend can gate access and force a rotation workflow.

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