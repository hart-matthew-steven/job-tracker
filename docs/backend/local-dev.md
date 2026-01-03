# Backend Local Development

This document describes how to run and work on the backend API locally.

---

## Requirements

- Python (version TBD)
- Virtual environment tool (venv, virtualenv, etc.)

---

## Running the Backend

From the repo root:

    cd backend
    # create and activate virtual environment
    # install dependencies
    # start the API server

Exact commands may vary and should be documented once finalized.

---

## Environment Configuration

- Configuration is provided via environment variables.
- `.env` files are local-only and must never be committed.
- A generated `backend/.env.example` file is used to document backend variable names (no values).

Do not document secret values.

### Database credentials

- Postgres settings come from `DB_HOST`, `DB_PORT`, `DB_NAME`, and `DB_SSLMODE` (set to `require` for both local tunnels and hosted providers).
- Two separate credentials are required:
  - `DB_APP_USER` / `DB_APP_PASSWORD`: runtime API user, scoped to read/write existing tables but **not** allowed to create or alter schema.
  - `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD`: Alembic migrations user, allowed to apply DDL during deploys.
- This split enforces least privilege so accidental schema changes cannot happen from the web app connection pool.
- Local development should provision both roles even if they point to the same database instance; grant the migrator role the additional `CREATE` / `ALTER` privileges only.
- Alembic (and any manual migration commands) must source `migrations_database_url`, while the application server keeps using `database_url` so it never escalates privileges.
- Legacy single-user vars (`DB_USER`, `DB_PASSWORD`) have been removed to make the separation explicit.

### Password policy

- Configure via `PASSWORD_MIN_LENGTH` (default 14).
- Password strength is enforced on registration/change/reset: min length, upper/lowercase, number, special char, denylist, and “no email/name in password”.
- Rotation is governed by Cognito; the legacy `password_changed_at`/`must_change_password` flow was removed during the cutover.

### Email verification (Resend)

- App-enforced email verification relies on the Resend SDK. Set the following env vars locally (see `.env.example`):
  - `EMAIL_VERIFICATION_ENABLED=true`
  - `EMAIL_VERIFICATION_CODE_TTL_SECONDS`, `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`, `EMAIL_VERIFICATION_MAX_ATTEMPTS`
  - `RESEND_API_KEY` (use a dev key) and `RESEND_FROM_EMAIL` (e.g., `Job Tracker <dev@jobapptracker.dev>`)
  - `FRONTEND_BASE_URL` (defaults to `http://localhost:5173`)
- Dev/testing can stub email delivery by pointing `RESEND_API_KEY` at a fake key and inspecting logs instead of sending live email.
- The `/auth/cognito/verification/send` and `/confirm` endpoints are public so you can request/confirm codes before logging in. Rate limiting still applies; keep the cooldown in mind when testing.

---

## Local Integrations

Development may include:
- local persistence (or dev database)
- AWS dev resources
- ngrok for external access (temporary)

Security rules still apply:
- do not bypass file scanning
- do not log secrets
- do not expose unnecessary endpoints

---

## Debugging Tips

- Enable structured logging (without secrets)
- Use request IDs for tracing
- Validate upload/scan flows end-to-end

---

## Updating this Document

Update this file when:
- backend startup process changes
- env/config expectations change
- local integration patterns change