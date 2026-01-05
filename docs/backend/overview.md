# Backend Overview

This document describes the backend structure and conventions at a high level.

---

## Stack

- Python API (FastAPI-style architecture)
- Persistence: PostgreSQL + SQLAlchemy
- Background processing: AWS-managed (EventBridge, Lambda)
- File scanning: AWS GuardDuty Malware Protection for S3
- Authentication: Cognito Option‑B (`/auth/cognito/*`) with Cloudflare Turnstile enforced on signup. Backend verifies Cognito access tokens on every request; access/id tokens live in memory + sessionStorage and refresh tokens live in sessionStorage only. No Job Tracker-specific JWT or refresh cookie remains.

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
- **CI/CD:** `.github/workflows/backend-deploy.yml` runs on pushes to `main`, assumes an AWS role via GitHub OIDC, builds/pushes the image, and executes `scripts/deploy_apprunner.py` to update App Runner, poll for health, and roll back automatically if a deployment fails. Manual runs are available through `workflow_dispatch`.

### Password policy

- Configurable via `PASSWORD_MIN_LENGTH` (default 14). Strength checks (mixed case, number, special, denylist, no email/name) apply whenever passwords are set.
- Rotation is handled by Cognito; the legacy `password_changed_at`/`must_change_password` fields were removed during the cutover.

---

## Responsibilities

- Owns business logic and persistence
- Provides a clean API contract to the frontend
- Handles uploads securely (scan-before-accept)
- Coordinates async jobs (scan, processing, analytics if added)
- Serves aggregate payloads when it meaningfully reduces latency. Example: `GET /jobs/{job_id}/details` now returns `{ job, notes, interviews, activity }` in a single call so the Jobs page no longer chains four sequential requests on every selection.

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

## Email delivery & verification

- Cognito currently sends only reset/notification emails via its default managed sender.
- Pre Sign-up Lambda (`lambda/cognito_pre_signup/`) auto-confirms users, which keeps Cognito from sending “confirm your account” emails.
- The backend now enforces email verification itself:
  - `email_verification_codes` table stores salted hashes, TTL, resend cooldown, attempt counts.
  - `POST /auth/cognito/verification/send` is a public, rate-limited endpoint that generates a 6-digit code and emails it via Resend (`RESEND_API_KEY`, `RESEND_FROM_EMAIL`).
  - `POST /auth/cognito/verification/confirm` validates the code, sets `users.is_email_verified` + `email_verified_at`, and calls Cognito `AdminUpdateUserAttributes` with `Username = cognito_sub` so AWS reflects the same state.
  - Middleware blocks all other APIs with `403 EMAIL_NOT_VERIFIED` until the DB flag is true (verification endpoints, logout, and `GET /users/me` are allowed so the UI can finish the flow).

---

## UI Preferences

- Per-user UI state (e.g., collapsed cards on the job details page) lives in `users.ui_preferences` (JSON).
- The SPA persists toggles via `PATCH /users/me/ui-preferences`, allowing the behavior to follow the user across browsers and future native clients.

---

## Updating this document

Update when:
- folder structure changes
- auth/session model changes
- persistence approach changes
- background job architecture changes