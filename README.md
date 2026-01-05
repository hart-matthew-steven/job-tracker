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
- Persists per-user UI preferences (e.g., collapsed cards) by calling `PATCH /users/me/ui-preferences`
- Automatically signs users out after a period of inactivity (default 30 minutes, configurable via `VITE_IDLE_TIMEOUT_MINUTES`)

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
- Stores per-user UI preferences in `users.ui_preferences` (JSON) and exposes them via `/users/me/ui-preferences`
- Optimized job-detail fetch via `GET /jobs/{job_id}/details`, which bundles the job, notes, interviews, and recent activity into one payload for the Jobs page

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

### Production deployment (AWS App Runner)

- The backend is deployed to **AWS App Runner** behind `https://api.jobapptracker.dev`.
- Runtime secrets (JWT secret, DB credentials, email/API keys, etc.) are provided via **AWS Secrets Manager** and injected into the App Runner service as environment variables, so they never live in the repo.
- Images are stored in Amazon ECR. Build and push from a trusted workstation/CI pipeline with `docker buildx` so the platform matches App Runner’s `linux/amd64` runtime (this flag is required even on Apple Silicon laptops; without it App Runner fails to start the container even though it runs locally).

```bash
export ACCOUNT_ID=<account_id>
export REGION=<region>
export REPO=<repo_name>
export TAG=<git-sha-or-version>
export IMAGE_URI=$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO

aws ecr get-login-password --region "$REGION" \
  | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

docker buildx build \
  --platform linux/amd64 \
  -t "$IMAGE_URI:$TAG" \
  --push \
  .
```

After the image is pushed, point the App Runner service at the new ECR tag (or update the service via IaC/console). App Runner pulls the image, injects environment variables from Secrets Manager, and exposes the service at the subdomain above.

## Authentication (Cognito – Production Cutover)

### Architecture overview

- The SPA talks **only** to our backend. `/auth/cognito/*` routes orchestrate Cognito SignUp / Confirm / Login / MFA / Refresh flows using the Cognito Identity Provider API (AuthFlow = `USER_PASSWORD_AUTH`, `SOFTWARE_TOKEN_MFA`, `REFRESH_TOKEN_AUTH`).
- Successful authentication returns the raw Cognito tokens (`access_token`, `id_token`, `refresh_token`, `expires_in`, `token_type`). No legacy Job Tracker JWTs or refresh cookies are minted.
- The backend enforces Cognito on every request:
  - Bearer tokens must be Cognito **access tokens** (`token_use == "access"`).
  - Signatures are validated via the User Pool JWKS with caching + rotation handling.
  - `sub` → JIT user provisioning keeps the relational data model in sync.
- Token refresh is available via `POST /auth/cognito/refresh` (Cognito `REFRESH_TOKEN_AUTH`). The frontend refreshes proactively ~60 seconds before expiry and deduplicates concurrent refresh calls.
- MFA is required (`SOFTWARE_TOKEN_MFA`). First login triggers `/auth/cognito/mfa/setup`; subsequent logins collect the 6-digit TOTP via `/auth/cognito/challenge`.

### Migration notes

- Legacy custom auth endpoints (`/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/verify`, `/auth/resend-verification`) and the JWT/refresh-cookie code path have been removed.
- User schema cleanup (`cognito_cutover_cleanup` migration) drops `password_hash`, `password_changed_at`, `token_version`, `is_email_verified`, `email_verified_at`, `refresh_tokens`, and `email_verification_tokens`. `cognito_sub` is now `NOT NULL` + unique.
- `.env.example` now only lists Cognito + core infrastructure variables.
- Frontend auth state lives in memory + `sessionStorage` (access/id tokens) with the refresh token kept in session storage only. Tabs stay in sync via a storage broadcast channel; no data is written to `localStorage`.
- `tokenManager.ts` centralizes persistence + refresh; API helpers automatically refresh once on 401 before logging the user out.
- Idle sessions: the SPA logs out automatically after ~30 minutes with no keyboard/mouse/touch activity (configurable via `VITE_IDLE_TIMEOUT_MINUTES`). This keeps Cognito settings unchanged while still expiring abandoned tabs.

### Security considerations

- **Token storage**: access/id tokens remain in memory + `sessionStorage`. Refresh tokens are stored in `sessionStorage` only (never cookies). Documentation recommends CSP (`default-src 'self'; script-src 'self' 'strict-dynamic' ...`) and dependency hygiene to mitigate XSS.
- **Authorization**: backend rejects any Bearer token that is not a Cognito access token signed with the expected key + `client_id`. Unknown `token_use` values are denied.
- **Logging**: no access/refresh/id token values are logged. Structured logs record only result codes (OK/CHALLENGE/FAIL) and anonymized Cognito subjects.
- **Rate limiting**: all `/auth/cognito/*` routes are decorated via SlowAPI. Enable `ENABLE_RATE_LIMITING=true` in prod and back the limiter with Redis/Elasticache.
- **CSRF**: there are no auth cookies. All requests are Bearer tokens via `Authorization` headers, which are not sent cross-site by browsers unless explicitly added.
- **MFA**: required for every user. QR secrets are shown once and never logged/persisted server-side. Existing devices can re-enroll via `/auth/cognito/mfa/setup` with an access token if needed.
- **CORS**: allow only the exact SPA origins in production (e.g., `https://jobapptracker.dev`). Local dev defaults (`http://localhost:5173`) are appended automatically when `ENV=dev`.

## Bot Protection (Cloudflare Turnstile)

**Why:** Automated signup storms burn Cognito quota (email/SMS/MFA) and can be used to stage AI abuse. Cloudflare Turnstile gives us a privacy-friendly CAPTCHA that we can verify server-side without degrading normal auth UX.

- `/auth/cognito/signup` requires a Turnstile token. Missing/invalid tokens return HTTP 400 “CAPTCHA verification failed”.
- Backend verification posts to `https://challenges.cloudflare.com/turnstile/v0/siteverify` (short timeout, no token logging). Missing configuration is fail-closed (HTTP 503 “Signup is temporarily unavailable”).
- CAPTCHA is enforced **only** on signup; login, confirmation, MFA, refresh, etc. remain unchanged.
- Env vars:
  - Backend (`.env.example`): `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`.
  - Frontend: `VITE_TURNSTILE_SITE_KEY` (or `window.__TURNSTILE_SITE_KEY__` while prototyping).
- Use Cloudflare’s public test keys for local dev (<https://developers.cloudflare.com/turnstile/get-started/>). Monitoring should alert on signup 4xx/5xx spikes in case CAPTCHA starts failing or abuse ramps up.

### Local development flow

1. Configure Cognito variables once (User Pool + App Client must already exist):
   ```bash
   export COGNITO_REGION=us-east-1
   export COGNITO_USER_POOL_ID=<your-pool-id>
   export COGNITO_APP_CLIENT_ID=<your-client-id>
   export TURNSTILE_SITE_KEY=<dev-turnstile-site-key>
   export TURNSTILE_SECRET_KEY=<dev-turnstile-secret-key>
   ```
2. Start the backend:
   ```bash
   cd backend
   ./venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
3. Start the frontend (the API base is the FastAPI URL):
   ```bash
   cd frontend-web
   export VITE_API_BASE_URL=http://localhost:8000
   export VITE_TURNSTILE_SITE_KEY=$TURNSTILE_SITE_KEY
   npm run dev
   ```
4. End-to-end flow:
   1. **Signup** – `/auth/cognito/signup` (name, email, strong password, Turnstile token).
   2. **Confirm** – `/auth/cognito/confirm` with the verification code Cognito emails you.
   3. **Login / MFA setup** – `/auth/cognito/login` → `/auth/cognito/mfa/setup` → `/auth/cognito/mfa/verify`.
   4. **Subsequent login** – `/auth/cognito/login` + `/auth/cognito/challenge` (SOFTWARE_TOKEN_MFA).
   5. **API calls** – SPA automatically attaches the Cognito access token to every request.

## Cognito Pre Sign-up Lambda

- Folder: `lambda/cognito_pre_signup/`
- Purpose: attached to the Cognito **Pre Sign-up** trigger so Cognito auto-confirms new users and skips its built-in verification emails. This keeps email ownership on our side for future Resend-based flows.
- Behavior: sets `autoConfirmUser=true` and `autoVerifyEmail=false` for supported trigger sources (`PreSignUp_SignUp`, `PreSignUp_AdminCreateUser`) and logs the trigger.
- No network calls, secrets, or external services. See the lambda README for build/push instructions and attach steps.

## Email verification (app-enforced)

- Cognito accounts are auto-confirmed, but the backend blocks all protected APIs with `403 EMAIL_NOT_VERIFIED` while `users.is_email_verified = false`.
- Signup automatically triggers the first verification email, so the `/verify` screen shows “code sent” and honors the resend cooldown before re-hitting the backend.
- Endpoints:
  - `POST /auth/cognito/verification/send` → throttled, public endpoint; generates a 6-digit code (hash + TTL) and emails it via Resend.
  - `POST /auth/cognito/verification/confirm` → validates the code, marks the DB record verified, and calls Cognito `AdminUpdateUserAttributes` with `Username=cognito_sub` / `email_verified=true`.
- Config knobs (see `.env.example`): `EMAIL_VERIFICATION_ENABLED`, `EMAIL_VERIFICATION_CODE_TTL_SECONDS`, `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`, `EMAIL_VERIFICATION_MAX_ATTEMPTS`, `RESEND_FROM_EMAIL`.
- Docs: `docs/auth-email-verification.md` (flow details, security notes, testing steps).

## Email Verification (App-enforced)

- Why: Cognito no longer sends confirmation emails (Pre Sign-up Lambda auto-confirms), but we still need trusted verification for AI billing and iOS parity. The app now owns verification end-to-end.
- Backend:
  - Config (`.env.example`): `EMAIL_VERIFICATION_ENABLED`, `EMAIL_VERIFICATION_CODE_TTL_SECONDS`, `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`, `EMAIL_VERIFICATION_MAX_ATTEMPTS`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FRONTEND_BASE_URL`.
  - Table `email_verification_codes` stores salted+hashed codes, TTL, attempts, resend cooldown.
  - Endpoints:
    - `POST /auth/cognito/verification/send` (public but rate limited) – generates a 6-digit code, stores hash, sends via Resend.
    - `POST /auth/cognito/verification/confirm` – validates code, marks `users.is_email_verified=true`, syncs `email_verified=true` back to Cognito using `Username=cognito_sub`.
  - Middleware blocks all other APIs with `403 EMAIL_NOT_VERIFIED` until the DB flag is true (only verification endpoints, logout, and `GET /users/me` stay open).
- Frontend:
  - Login fetches `/users/me`; if unverified it automatically requests a code and routes to `/verify`.
  - `/verify` screen allows resend (default 60s cooldown) and confirmation.
  - Any 403 EMAIL_NOT_VERIFIED automatically redirects back to `/verify`.
- Resend: Uses the official Python SDK; no raw codes logged. Emails are short, code-only, and mention the 15-minute expiry.

### Refresh flow testing

The login response includes `refresh_token`. To test refresh manually:

```bash
REFRESH="copy-from-login-response"
curl -s -X POST http://localhost:8000/auth/cognito/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"$REFRESH\"}"
```

You’ll receive a new `access_token`/`id_token`. The SPA’s `tokenManager` does the same automatically when the access token is about to expire; you can watch the network tab for `/auth/cognito/refresh` to verify single-flight behaviour.

### Production readiness checklist

- [ ] `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID` present in App Runner/Secrets Manager.
- [ ] CORS origins limited to `https://jobapptracker.dev` + `https://www.jobapptracker.dev`.
- [ ] `ENABLE_RATE_LIMITING=true` with SlowAPI backed by Redis/Elasticache.
- [ ] CloudFront (or ALB) configured with CSP/HSTS (`strict-transport-security: max-age=63072000; includeSubDomains; preload`).
- [ ] Cognito App Client configured with `USER_PASSWORD_AUTH`, `REFRESH_TOKEN_AUTH`, and MFA = SOFTWARE_TOKEN_MFA (required).
- [ ] Frontend built with `VITE_API_BASE_URL=https://api.jobapptracker.dev`.
- [ ] Monitoring/alerting wired for `/auth/cognito/*` 4xx/5xx spikes and limiter throttling.

### What's next

- Passkeys + native iOS flows (future chunk)
- AI usage/billing gates (future chunk)

### CI/CD pipelines

Production deploys are now automated through GitHub Actions:

- **Backend** — `.github/workflows/backend-deploy.yml`
  - Triggers on pushes to `main` that touch `backend/**`, the deploy script, or the workflow.
  - Uses GitHub OIDC to assume `AWS_ROLE_ARN_BACKEND`, builds the Docker image with `docker build` (linux/amd64), tags/pushes to ECR, then runs `scripts/deploy_apprunner.py` to update the App Runner service, wait for health, and roll back automatically if needed.
  - Can also be run manually via `workflow_dispatch` for hotfixes.
- **Frontend** — `.github/workflows/frontend-deploy.yml`
  - Triggers on pushes to `main` that touch `frontend-web/**`, the deploy script, or the workflow.
  - Builds the Vite site with injected `VITE_API_BASE_URL`, uploads the `dist/` artifacts to versioned `releases/<id>/` prefixes in S3, promotes the release to the bucket root, updates the `_releases/current.json` pointer, invalidates CloudFront, and optionally health-checks the public site. All rollout/rollback logic lives in `scripts/deploy_frontend.py`.

Both workflows use environment protection rules (`environment: prod`) and a shared concurrency key to avoid overlapping deployments.

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

- `GUARD_DUTY_ENABLED` (default `false`): enable AWS GuardDuty malware callbacks. When disabled, the callback endpoints no-op so local dev can run without GuardDuty or secrets.

### Password policy

- Minimum length: `PASSWORD_MIN_LENGTH=14` by default.
- Strength checks (mixed case, number, special char, denylist, no email/name inclusion) run whenever a password is set/changed (e.g., Cognito signup helper).
- Rotation-specific fields (`password_changed_at`, `PASSWORD_MAX_AGE_DAYS`, `must_change_password`) were removed once Cognito became the sole auth provider; future rotation is governed by Cognito policies.
- The backend is the source of truth; the frontend mirrors the rules for UX-only validation.

- Email verification is enforced by the app: after signup we route users to `/verify` to request/confirm a 6-digit code via Resend (`/auth/cognito/verification/send` + `/auth/cognito/verification/confirm`). If someone tries to log in before verifying, every protected API still returns `403 EMAIL_NOT_VERIFIED` and the UI redirects back to `/verify`. Once verified, the backend marks `users.is_email_verified = true` and syncs `email_verified=true` to Cognito via `AdminUpdateUserAttributes` so native clients stay in sync. Settings + flow docs live in `docs/auth-email-verification.md`.
- Idle timeout (frontend): `VITE_IDLE_TIMEOUT_MINUTES` (optional, default 30, minimum 5) controls how long the SPA waits before logging out an inactive tab.
- Idle timeout (frontend): `VITE_IDLE_TIMEOUT_MINUTES` (optional, default 30) controls how long the SPA waits before logging out a tab with no activity.

## Design Principles

- Small, reviewable changes
- Clear separation of concerns
- Explicit structure over hidden conventions
- AI-assisted development with human review and version-controlled memory