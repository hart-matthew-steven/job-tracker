# Job Tracker

A personal job application tracking system with a React (Vite) frontend and a Python backend API.

This repository is intentionally structured to keep source code, documentation, execution output, and one-off scripts clearly separated. The goal is to make the project easy to understand, maintain, and extend—both for personal use and for external reviewers.

---

## Repository Structure

    job-tracker/
    ├── frontend-web/        # React + Vite application
    ├── backend/             # Python API
    ├── docs/                # Project documentation (including AI-generated summaries)
    ├── logs/                # Script output and run results (not source-of-truth)
    ├── temp_scripts/        # One-off or exploratory scripts (disposable by default)
    └── .cursor/             # Cursor rules and AI behavior configuration

---

## High-Level Architecture

At a high level, the system consists of:

- A React frontend for user interaction
- A Python backend API for business logic and persistence
- AWS-managed infrastructure for storage, background processing, and security controls
- Supporting services for file scanning and operational safety

Development vs Production:
- **Development:** the backend API may be exposed via ngrok to support local development, webhooks, and external integrations
- **Production:** the backend runs behind AWS-managed networking and security controls

Security considerations:
- File scanning is implemented via **AWS GuardDuty Malware Protection for S3**.
- Uploaded documents are scanned automatically by AWS; download is blocked unless `scan_status=CLEAN`.
- See `docs/architecture/security.md` for details.

Detailed architecture diagrams and data-flow documentation live under:
- `docs/architecture/overview.md`
- `docs/architecture/data-flow.md`
- `docs/architecture/security.md`

---

## Frontend

Location: `frontend-web/`  
Stack: React + Vite (TypeScript)

Responsibilities:
- User interface for tracking job applications and statuses
- Views for notes, documents, and related metadata
- Communication with the backend via a centralized API client

Common entry points:
- `frontend-web/src/main.tsx`
- `frontend-web/src/App.tsx`

Frontend-specific documentation (if present) lives under:
- `docs/frontend/`

---

## Backend

Location: `backend/`  
Stack: Python API (FastAPI-style architecture)

Responsibilities:
- Authentication and session handling (if applicable)
- API endpoints for job applications, notes, and related resources
- Data validation, persistence, and error handling
- Integration with background processing and security services

Typical structure:

    backend/app/
    ├── routes/      # HTTP route definitions
    ├── services/    # Business logic
    ├── models/      # Database models
    ├── schemas/     # Request/response schemas
    ├── core/        # Configuration, auth, and shared utilities

Backend-specific documentation (if present) lives under:
- `docs/backend/`

### Backend Docker

- **Build** (local/App Runner-ready image):

  ```bash
  cd backend
  docker build -t jobtracker-backend .
  ```

- **Run locally** (supply env vars at runtime; `.env` stays outside the image):

  ```bash
  docker run --rm -p 8000:8000 \
    --env-file backend/.env \
    jobtracker-backend
  ```

  The container listens on `0.0.0.0:${PORT:-8000}` so App Runner can inject `PORT`.

- **Docker Compose (optional local stack)**:

  ```bash
  docker compose up --build
  ```

  This starts Postgres + the backend using non-secret defaults. Override any values by exporting env vars or passing your own env file—avoid editing `.env` directly in the repo since the container never copies it.
  The Postgres container now runs an init script (only the first time the volume is created) that provisions the local `DB_APP_USER` / `DB_MIGRATOR_USER` roles. If you already had an existing volume before this change, run `docker compose down -v` once to recreate it so the script executes, then `docker compose up --build` again.

  **Local Docker debugging checklist**

  1. **Reset Postgres volume (only if the credentials/scripts changed):**

     ```bash
     docker compose down -v
     ```

  2. **Start the services:**

     ```bash
     docker compose up --build
     ```

  3. **Apply migrations inside the backend container:**

     ```bash
     docker compose exec backend alembic upgrade head
     ```

  4. **(Only if you kept an existing volume)** grant privileges manually so the runtime user can see tables created before the init script existed:

     ```bash
     docker compose exec db psql -U jobtracker -d jobtracker \
       -c "GRANT USAGE ON SCHEMA public TO jobtracker_app; \
           GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO jobtracker_app; \
           GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO jobtracker_app; \
           ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public GRANT SELECT,INSERT,UPDATE,DELETE ON TABLES TO jobtracker_app; \
           ALTER DEFAULT PRIVILEGES FOR ROLE jobtracker_migrator IN SCHEMA public GRANT USAGE,SELECT ON SEQUENCES TO jobtracker_app;"
     ```

     Skip this when you start from a fresh volume—the init script already grants the rights.

  5. **Verify a user when email delivery is disabled locally:**

     ```bash
     docker compose exec backend python -c "from app.core.security import create_email_verification_token; from app.core.config import settings; email='<EMAIL>'; token=create_email_verification_token(email); print(f'{settings.FRONTEND_BASE_URL}/verify?token={token}&email={email}')"
     ```

     Copy the printed URL into your browser to mark the account verified. Afterwards you can log in normally.

---

## Documentation

All project documentation lives under the `docs/` directory.

AI-assisted development is supported via a small set of version-controlled files:
- `docs/ai/MEMORY.md` — rolling summary of current project state and recent work
- `docs/ai/DECISIONS.md` — ADR-lite decision log (what was chosen and why)
- `docs/ai/MAP.md` — high-level map of key folders and entry points

These files are intentionally concise and updated incrementally as the project evolves.

---

## Logs

The `logs/` directory contains output from script executions, refactor runs, and other non-authoritative artifacts.

Rules:
- Logs are ignored by default in Git
- Logs are not source-of-truth documentation
- Any log worth keeping should be committed intentionally

---

## Temporary Scripts

The `temp_scripts/` directory is reserved for one-off or exploratory scripts such as:
- data migrations
- investigations
- refactor support utilities

Rules:
- Scripts here are disposable by default
- They should not be imported by production code
- If a script becomes permanent, it should be moved into an appropriate source directory

---

## Development (High-Level)

Frontend:

    cd frontend-web
    npm install
    npm run typecheck
    npm run lint
    npm test
    npm run dev

CI:

    # GitHub Actions runs these checks on pull requests (and on pushes to main).
    # Branch protection steps: see docs/ci/github-actions.md

Backend:

    cd backend
    # create virtual environment
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

    # run tests
    python3 -m pytest

    # run the API (example)
    python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

See `docs/` for deeper or component-specific documentation as the project evolves.

---

## Environment Variables (high-level)

The backend and frontend are configured via environment variables.

- **Backend**: see `backend/app/core/config.py` (values come from process env; local dev may use `.env`)
- **Frontend**: Vite env vars (see `VITE_*`)

This repo includes a generated `backend/.env.example` (**names only**, no values) based on variables referenced in backend code.

### Database credentials

- Shared parameters: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_SSLMODE` (set to `require` for every environment so TLS is enforced).
- Runtime API connections use `DB_APP_USER` / `DB_APP_PASSWORD`. This user is scoped to CRUD/data access and must **not** have permission to create or alter tables.
- Alembic migrations use `DB_MIGRATOR_USER` / `DB_MIGRATOR_PASSWORD`. This user holds the elevated privileges needed for schema changes and should be used only during deploys or manual migration runs.
- The backend exposes two URLs via config: `database_url` (app user) and `migrations_database_url` (migrator). Always select the one that matches the task you are running.
- Local development should create both roles, even if they initially share the same password, to mirror production least-privilege behavior.
- Legacy `DB_USER` / `DB_PASSWORD` vars have been removed; define both `DB_APP_*` and `DB_MIGRATOR_*` explicitly.

### Optional integrations

- `EMAIL_ENABLED` (default `false`): enable outbound email delivery. When disabled, the backend no-ops and logs instead of calling providers. When enabled, configure `EMAIL_PROVIDER` + required credentials.
- `GUARD_DUTY_ENABLED` (default `false`): enable AWS GuardDuty malware callbacks. When disabled, the callback endpoints no-op so local dev can run without GuardDuty or secrets.

### Password policy & rotation

- Defaults: `PASSWORD_MIN_LENGTH=14`, `PASSWORD_MAX_AGE_DAYS=90`.
- Strength checks (min length, mixed case, number, special char, denylist, no email/name inclusion) apply whenever a password is set or changed (registration, change password, reset flows). Existing stored passwords continue to work until rotated.
- Rotation uses `password_changed_at` with the configured `PASSWORD_MAX_AGE_DAYS`. Logins succeeding with expired passwords still receive tokens, but every auth response (login/refresh/`GET /users/me`) includes `must_change_password: true` so the frontend can block access and redirect to the Change Password screen.
- Configure the policy via the env vars above; the backend is the source of truth, and the frontend mirrors the rules for UX-only validation.

### Email providers

`EMAIL_PROVIDER` controls how verification emails are sent:

- **`resend` (default)**: Resend API
  - Requires: `FROM_EMAIL`, `RESEND_API_KEY`
- **`ses`**: AWS SES via `boto3`
  - Requires: `AWS_REGION`, `FROM_EMAIL`
- **`gmail`**: SMTP (preserves `SMTP_FROM_EMAIL` as the From address)
  - Requires: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`
- **Legacy alias**: `smtp` is treated as `gmail`

Notes:
- `FROM_EMAIL` is used **only** for `ses` and `resend`.
- `AWS_REGION` is used for AWS clients (including SES).

## Design Principles

- Small, reviewable changes
- Clear separation of concerns
- Explicit structure over hidden conventions
- AI-assisted development with human review and version-controlled memory