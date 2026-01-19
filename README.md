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
- Kanban board (`/board`) with drag-and-drop swimlanes, right-side drawer, momentum controls, and follow-up suggestions
- Legacy list view (`/jobs`) and detail forms for notes, documents, activity, and reminders
- Global search modal (⌘K / Ctrl+K) that calls `/jobs/search` and deep-links into the drawer
- Icon-only navigation shell + activity pulse widget, with per-user preferences persisted via `PATCH /users/me/ui-preferences`
- Automatically signs users out after a period of inactivity (default 30 minutes, configurable via `VITE_IDLE_TIMEOUT_MINUTES`)

UI highlights:

- **Momentum mode:** one-tap follow-up/apply/reminder actions update `last_action_at`/`next_action_at` and resurface stale roles.
- **Smart suggestions:** cards flagged as `needs_follow_up` float to the board header for quick triage.
- **Command palette:** `⌘K` / `Ctrl+K` opens the global search modal and selects a job directly in the drawer.
- **Marketing landing page + demo:** `/` showcases the product with hero + feature grid + CTA buttons, and the “View demo board” CTA links to `/demo/board` so prospects can explore a read-only kanban preview without signing in.

Common entry points:
- `frontend-web/src/main.tsx`
- `frontend-web/src/App.tsx`

Frontend-specific documentation lives under `docs/frontend/` (see `docs/frontend/overview.md` for the board-first component map and responsive shell notes).

---

## Backend

Location: `backend/`  
Stack: Python API (FastAPI-style architecture)

Responsibilities:
- Authentication and enforcement of Cognito access tokens
- API endpoints for job applications, notes, interviews, documents, UI preferences, board/search/metrics helpers
- Data validation, persistence, and error handling
- Integration with GuardDuty malware scanning plus other security services
- Stores per-user UI preferences in `users.ui_preferences` (JSON) and exposes board/search telemetry via `/jobs/board`, `/jobs/search`, and `/jobs/metrics/activity`
- Optimized job-detail fetch via `GET /jobs/{job_id}/details`, which bundles the job, notes, interviews, and recent activity into one payload for the drawer

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

#### Secrets bundle (`SETTINGS_BUNDLE_SECRET_ARN`)

- Instead of managing dozens of App Runner env vars manually, create a single AWS Secrets Manager entry that contains the entire `.env` payload as JSON. The backend boots by loading the secret referenced by `SETTINGS_BUNDLE_SECRET_ARN`, parsing the JSON, and hydrating `os.environ` before the regular settings code runs. This works for both the API service and the Celery worker.
- Helper script:

  ```bash
  # Convert your .env into JSON suitable for Secrets Manager
  python temp_scripts/env_to_json.py backend/.env > /tmp/backend-config.json

  # Upload /tmp/backend-config.json as the secret value (e.g., jobtracker/prod/backend-config)
  ```

- Set `SETTINGS_BUNDLE_SECRET_ARN=arn:aws:secretsmanager:...:secret:jobtracker/prod/backend-config` in App Runner (and locally in `.env`). The JSON can include `ENV`, DB creds, API keys, etc., while keeping App Runner well under its 50-variable limit.

### Rate limiting (DynamoDB)

- Request-level limits (for `/auth/cognito/*`, `/ai/*`, and document upload presigns) use the shared DynamoDB table `jobapptracker-rate-limits`.
- Key design:
  - `pk = user:{user_id}` for authenticated requests or `ip:{client_ip}` for anonymous callers.
  - `sk = route:{route_key}:window:{window_seconds}`.
  - Attributes: `window_start`, `count`, and `expires_at`. DynamoDB’s TTL evicts expired windows automatically so App Runner instances stay in sync without Redis/ElastiCache.
- The FastAPI dependency `require_rate_limit(route_key, limit, window_seconds)` increments the counter via `UpdateItem` with a conditional expression. If the count exceeds the configured limit we raise HTTP 429 with a `Retry-After` header before touching business logic (or credits).
- Configuration knobs (defaults are dev-friendly): `RATE_LIMIT_ENABLED`, `DDB_RATE_LIMIT_TABLE`, `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`, `RATE_LIMIT_DEFAULT_MAX_REQUESTS`, plus the AI-specific values `AI_RATE_LIMIT_WINDOW_SECONDS` / `AI_RATE_LIMIT_MAX_REQUESTS`.
- Local development keeps the limiter disabled (`RATE_LIMIT_ENABLED=false`). To exercise it locally, set the env vars above and provide AWS credentials with DynamoDB access; otherwise the Noop limiter is used.

#### Observability & admin controls

- Every limiter decision emits a structured JSON log (`user_id`, `route`, `http_method`, `limiter_key`, `window_seconds`, `limit`, `count`, `remaining`, `reset_epoch`, `decision`). Use CloudWatch/Log Insights to answer “who is being throttled?” without scraping HTTP responses.
- `/admin/rate-limits/status`, `/admin/rate-limits/reset`, and `/admin/rate-limits/override` are admin-only (Cognito + `users.is_admin=true`) and provide the sanctioned way to inspect or tweak limits for a single user. Overrides write `sk=override:global` with `{limit, window_seconds, ttl_seconds}` and expire automatically via Dynamo TTL.
- Admins are created manually—there is no public promotion endpoint. Run:

  ```sql
  UPDATE users SET is_admin = true WHERE email = 'you@example.com';
  ```

  Grant access sparingly; everything is logged.

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
- **Rate limiting**: `/auth/cognito/*`, `/ai/*`, and document upload routes share a DynamoDB-backed limiter (`jobapptracker-rate-limits`). Each request increments `{pk=user:{id}|ip:{addr}, sk=route:{route_key}:window:{seconds}}` with a TTL-based expiry. Enable it in prod via `RATE_LIMIT_ENABLED=true`, `DDB_RATE_LIMIT_TABLE`, and `AWS_REGION`; local dev can leave it disabled to avoid AWS dependencies.
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

## Rate Limiting (DynamoDB)

- **Why DynamoDB?** App Runner services can scale horizontally at any time, so the old in-memory/SlowAPI limiter either had to run on a single instance or risk being bypassed. DynamoDB gives us per-item conditional updates, TTL expiry, and essentially zero maintenance without introducing Redis/ElastiCache.
- **Table layout:** `pk=user:{user_id}` (or `ip:{remote_addr}` for unauthenticated requests), `sk=route:{route_key}:window:{seconds}`, attributes `window_start`, `count`, `expires_at` (used for TTL). Every request runs a single `UpdateItem`. If the `window_start` has changed, the limiter resets the counter and starts a new window.
- **Config knobs:** `RATE_LIMIT_ENABLED`, `DDB_RATE_LIMIT_TABLE`, `RATE_LIMIT_DEFAULT_WINDOW_SECONDS`, `RATE_LIMIT_DEFAULT_MAX_REQUESTS`, plus AI-specific knobs `AI_RATE_LIMIT_WINDOW_SECONDS`/`AI_RATE_LIMIT_MAX_REQUESTS`. Local `.env` leaves the limiter disabled by default; set those vars plus `AWS_REGION` to exercise it.
- **Where it applies:** `/ai/chat`, `/ai/conversations*`, `/ai/demo`, `/auth/cognito/*`, and `/jobs/{id}/documents/presign-upload`. Rate-limited endpoints return HTTP 429 with a `Retry-After` header and `details.retry_after_seconds` payload.
- **Manual test:**

  ```bash
  export RATE_LIMIT_ENABLED=true
  export DDB_RATE_LIMIT_TABLE=jobapptracker-rate-limits
  export AWS_REGION=us-east-1  # adjust as needed
  ACCESS="Bearer $(cat /tmp/access_token)"
  for i in {1..12}; do
    curl -s -o /dev/null -w "%{http_code}\n" \
      -H "Authorization: $ACCESS" \
      -H "Content-Type: application/json" \
      -d '{"request_id":"limit-test","messages":[{"role":"user","content":"hi"}]}' \
      http://localhost:8000/ai/chat
  done
  ```

  The first few calls return 200; subsequent ones return 429 with `Retry-After`.

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
   1. **Signup** – `/auth/cognito/signup` (name, email, strong password, Turnstile token). Pre Sign-up Lambda auto-confirms the account so Cognito doesn’t send its own email.
   2. **Verify email (app-enforced)** – `/auth/cognito/verification/send` issues the 6-digit code, `/auth/cognito/verification/confirm` validates it and unlocks the account. The SPA routes to `/verify` right after signup and retries if a login hits `403 EMAIL_NOT_VERIFIED`.
   3. **Login / MFA setup** – `/auth/cognito/login` → `/auth/cognito/mfa/setup` → `/auth/cognito/mfa/verify`.
   4. **Subsequent login** – `/auth/cognito/login` + `/auth/cognito/challenge` (SOFTWARE_TOKEN_MFA).
   5. **API calls** – SPA automatically attaches the Cognito access token to every request.

## Cognito signup & verification internals

- **Pre Sign-up Lambda** (`lambda/cognito_pre_signup/`) is attached to Cognito’s Pre Sign-up trigger. It sets `autoConfirmUser=true` / `autoVerifyEmail=false`, performs no network calls, and simply logs the trigger so Cognito stops emailing confirmation codes. Accounts land in `CONFIRMED` state immediately and the product owns all verification UX.
- **App-enforced verification**:
  - Signup auto-generates the first 6-digit code (salted SHA-256 hash + TTL/cooldown/attempt caps) and sends it via Resend; the `/verify` page shows “code sent” plus the cooldown countdown.
  - `POST /auth/cognito/verification/send` is a public, rate-limited endpoint that regenerates the code and returns `resend_available_in_seconds`.
  - `POST /auth/cognito/verification/confirm` validates the code, marks `users.is_email_verified` / `email_verified_at`, and calls Cognito `AdminUpdateUserAttributes` (`Username=cognito_sub`, `email_verified=true`) so native clients stay consistent.
  - Middleware blocks every other API (besides verification endpoints, logout, and `GET /users/me`) with `403 EMAIL_NOT_VERIFIED` until the DB flag is true.
  - Config knobs (`.env.example`): `EMAIL_VERIFICATION_ENABLED`, `EMAIL_VERIFICATION_CODE_TTL_SECONDS`, `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS`, `EMAIL_VERIFICATION_MAX_ATTEMPTS`, `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FRONTEND_BASE_URL`.
- See `docs/architecture/cognito-option-b.md` and `docs/architecture/security.md` for the full sequence diagrams and threat model.

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
- [ ] `RATE_LIMIT_ENABLED=true` with `DDB_RATE_LIMIT_TABLE` + IAM allowing `dynamodb:UpdateItem/DescribeTable` for the limiter table.
- [ ] CloudFront (or ALB) configured with CSP/HSTS (`strict-transport-security: max-age=63072000; includeSubDomains; preload`).
- [ ] Cognito App Client configured with `USER_PASSWORD_AUTH`, `REFRESH_TOKEN_AUTH`, and MFA = SOFTWARE_TOKEN_MFA (required).
- [ ] Frontend built with `VITE_API_BASE_URL=https://api.jobapptracker.dev`.
- [ ] Monitoring/alerting wired for `/auth/cognito/*` 4xx/5xx spikes and limiter throttling.

### What's next

- Passkeys + native iOS flows (future chunk)
- AI usage/billing gates (future chunk)

### Stripe prepaid credits (Phase A)

- Credits are sold in fixed packs configured via `STRIPE_PRICE_MAP` (`pack_key:price_id:credits`). The backend accepts only a `pack_key`, resolves the Stripe Price ID + credit quantity, and writes that metadata (`user_id`, `pack_key`, `credits_to_grant`, `environment`) into the Checkout Session and PaymentIntent so clients cannot spoof amounts.
- Users are linked to Stripe Customers (`users.stripe_customer_id`). `GET /billing/credits/balance`/`GET /billing/me` return the current balance, lifetime grants/spend, Stripe customer id (if present), and the latest `credit_ledger` rows (with pack + Stripe ids). This is the UI/SDK-friendly surface for displaying "credits left".
- `/billing/stripe/webhook` is the sole minting path. Every event is inserted into `stripe_events` with `status=pending` before any business logic runs; the handler verifies `checkout.session.completed` events are paid, uses the metadata to locate the user + pack, inserts a single ledger entry (`source=stripe`, `source_ref=stripe_event_id`, `pack_key`, `idempotency_key`), and updates `stripe_events.status` to `processed|skipped`. Failures mark the row `failed`, capture the error, and return HTTP 500 so Stripe retries.
- Paid feature enforcement happens in two steps so flaky AI calls never double charge:
  1. `reserve_credits(user_id, amount, idempotency_key)` locks the user row and inserts an `entry_type=ai_reserve` ledger row (negative amount, status `reserved`, correlation id). If there aren’t enough funds it raises `InsufficientCreditsError` and the API surfaces HTTP 402.
  2. On success we either:
     - `finalize_charge(reservation_id, actual_amount, idempotency_key)` → writes `ai_release` (+reserved amount) followed by `ai_charge` (−actual cost) so the ledger nets to the true spend; or
     - `refund_reservation(reservation_id, idempotency_key)` → writes `ai_refund` (+reserved) and marks the hold as refunded.
  Each call supplies a unique idempotency key, so retried requests reuse the existing rows instead of double spending.
- `POST /ai/chat` applies the same primitives in production: we run the payload through OpenAI’s tokenizer (`tiktoken`) to count prompt tokens, budget `AI_COMPLETION_TOKENS_MAX` completion tokens, add the configured buffer (`AI_CREDITS_RESERVE_BUFFER_PCT`, default 25%), reserve that total, call OpenAI, then finalize/refund based on actual usage. If OpenAI returns more tokens than were reserved the hold is refunded automatically and the API responds with HTTP 500 so the client can retry safely (no silent overruns).
- `POST /ai/demo` remains available for engineers when `ENABLE_BILLING_DEBUG_ENDPOINT=true` to exercise the reserve/finalize/refund flow without calling OpenAI.
- Local test loop:

```bash
# 1. Start uvicorn /run backend and forward webhooks locally
stripe login
stripe listen --forward-to http://localhost:8000/billing/stripe/webhook

# 2. Create a checkout session for a configured pack (e.g., "starter")
ACCESS="Bearer $(cat /tmp/access_token)"   # or copy from SPA devtools
curl -s -X POST http://localhost:8000/billing/stripe/checkout \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"pack_key":"starter"}'
# -> open checkout_url, use Stripe test card 4242-4242-4242-4242 (any CVC/ZIP)

# 3. Confirm credits were granted
curl -s -H "Authorization: $ACCESS" http://localhost:8000/billing/me | jq

# 4. (Optional, non-prod only) burn credits via debug helper
curl -s -X POST http://localhost:8000/billing/credits/debug/spend \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"amount_cents":250,"reason":"dev test","idempotency_key":"debug-1"}'

# 5. Exercise the reservation/finalize/refund flow without OpenAI
curl -s -X POST http://localhost:8000/ai/demo \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"idempotency_key":"demo-123","estimated_cost_credits":1200,"simulate_outcome":"success","actual_cost_credits":900}'

# 6. Call the production AI chat endpoint (over-reserves + settles automatically)
curl -s -X POST http://localhost:8000/ai/chat \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{
        "request_id": "chat-1",
        "messages": [
          {"role": "system", "content": "You are a concise assistant."},
          {"role": "user", "content": "Summarize my weekly wins."}
        ]
      }'
```

### AI conversations + guardrails

- Durable storage lives in `ai_conversations` (per conversation) and `ai_messages` (per message). `ai_usage` rows now link back to both the conversation and the assistant message so every OpenAI call has a single usage/ledger footprint.
- New endpoints:
  - `POST /ai/conversations` – creates a conversation; optional `message` triggers an immediate completion.
  - `GET /ai/conversations` – lists the authenticated user’s conversations (paged by `limit`/`offset`).
  - `GET /ai/conversations/{id}` – returns metadata + paged messages (oldest-first).
  - `POST /ai/conversations/{id}/messages` – appends a user message, runs the OpenAI workflow, persists the assistant reply, and returns `{user_message, assistant_message, credits_used_cents, credits_refunded_cents, credits_reserved_cents, credits_remaining_*}`.
  - `PATCH /ai/conversations/{id}` – updates the conversation title (pass `null`/omit to clear it) and returns the refreshed thread metadata.
- `GET /ai/config` – returns `{ "max_input_chars": AI_MAX_INPUT_CHARS }` so the SPA can size its textarea/counter dynamically whenever the backend budget changes.
- `ai_messages.balance_remaining_cents` stores the user’s post-response balance so the SPA can show “Remaining credits” per assistant bubble alongside the existing token/charge metadata. Both `POST /ai/conversations` (when `message` is provided) and `POST /ai/conversations/{id}/messages` now accept an optional `purpose` (`cover_letter`, `thank_you`, `resume_tailoring`); the service injects the relevant system prompt without polluting the stored transcript.
- Frontend entry point: `/ai-assistant` adds a primary nav item, renders the conversation list + chat thread full-screen, and uses the shared CreditsContext to disable the composer when the balance hits zero. The composer now defaults to “General chat” while keeping optional presets for cover letters / thank-you letters / resume tailoring. Each conversation card exposes an action menu (rename + delete) that works on desktop and mobile. HTTP 402 responses show a friendly banner with a “Buy credits” CTA that routes to `/billing`; `GET /ai/conversations*` history calls never spend credits.
- Guardrails: per-user rate limiting (`AI_REQUESTS_PER_MINUTE`), concurrency limiting (`AI_MAX_CONCURRENT_REQUESTS`), context trimming (`AI_MAX_CONTEXT_MESSAGES`), max user input (`AI_MAX_INPUT_CHARS`), retry budget (`AI_OPENAI_MAX_RETRIES`), and a higher completion cap (`AI_COMPLETION_TOKENS_MAX=3000`). All are documented in `.env.example` and parsed in `app/core/config.py`.
- Settlement logic now handles overruns safely: if actual cost exceeds the reservation we finalize the reserved amount, attempt to spend the delta via `CreditsService.spend_credits`, and refund/return HTTP 402 when the user lacks funds—no negative balances or silent absorption.
- Context meter: `GET /ai/conversations/{id}` now returns `context_status` (tokens used vs `AI_CONTEXT_TOKEN_BUDGET`, percent full, last summarized timestamp) so the UI can display “Context 80% full” indicators similar to Cursor.
- Summaries: once a conversation crosses `AI_SUMMARY_MESSAGE_THRESHOLD`/`AI_SUMMARY_TOKEN_THRESHOLD`, the backend generates a rolling summary (stored in `ai_conversation_summaries`) and injects it into subsequent prompts so the model retains older context. Summary tuning is controlled via `AI_SUMMARY_*` settings.
- Example conversation loop (after seeding credits):

```bash
# Create a conversation with an initial prompt
curl -s -X POST http://localhost:8000/ai/conversations \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"title":"Resume polish","message":"Review my summary"}' | jq

# List conversations
curl -s -H "Authorization: $ACCESS" http://localhost:8000/ai/conversations | jq

# Fetch the latest messages (conversation id 42 shown here)
curl -s -H "Authorization: $ACCESS" http://localhost:8000/ai/conversations/42?limit=20 | jq

# Send another message within the same conversation
curl -s -X POST http://localhost:8000/ai/conversations/42/messages \
  -H "Authorization: $ACCESS" \
  -H "Content-Type: application/json" \
  -d '{"content":"Draft a thank-you email for Acme"}' | jq
```

### AI artifacts & background processing

- Resume / job-description context is managed through first-class “artifacts.” The backend exposes:
- `POST /ai/artifacts/upload-url` → presigned PUT for S3 + artifact placeholder
- `POST /ai/artifacts/{id}/complete-upload` → enqueues extraction (docx/pdf)
- `POST /ai/artifacts/text` → stores pasted resumes/JDs immediately
- `POST /ai/artifacts/url` → scrapes a JD webpage via readability + BeautifulSoup
- `POST /ai/artifacts/{id}/pin` → reuse an existing artifact in another conversation
- `GET /ai/artifacts/conversations/{id}` → returns one entry per role with `{ role, artifact_id, version_number, status, source_type, created_at, pinned_at, failure_reason, view_url }`
- `GET /ai/artifacts/conversations/{id}/history?role=resume` → returns every version for the specified role (ordered newest → oldest) so the UI can show pinned history/version numbers.
- `GET /ai/artifacts/{artifact_id}/diff?compare_to=<optional>` → returns a structured diff between the requested artifact and the previous version (or the `compare_to` id). The backend performs a line-level diff on the stored text content and emits `{op: equal|insert|delete|replace, text}` rows for UI rendering.
- Storage & queue configuration:
  - `AI_ARTIFACTS_BUCKET` — dedicated S3 bucket for AI uploads
  - `AI_ARTIFACTS_S3_PREFIX` — path prefix (default `users/`)
  - `AI_ARTIFACTS_SQS_QUEUE_URL` — SQS queue consumed by the Celery worker
  - `MAX_ARTIFACT_VERSIONS` — per-user retention cap (older uploads trimmed automatically)
- Celery worker:
  - Lives in the same repo (`app/celery_app.py`, tasks under `app/tasks/artifacts.py`)
  - Broker is SQS (`broker_url=sqs://`, predefined queue = `artifact-tasks`)
  - Tasks use `python-docx`, `pdfplumber`, `pypdfium2`, and `readability-lxml` to normalize text before saving it back to the artifact record.
  - Local dev can run the worker with:

    ```bash
    cd backend
    ./venv/bin/celery -A app.tasks.artifacts worker --loglevel=info
    ```

    (Set `AI_ARTIFACTS_SQS_QUEUE_URL` + AWS creds, or leave it empty to fall back to in-memory execution for smoke tests.)
- App Runner deploys a **second service** for the worker (same image, command `/app/scripts/run_celery_worker.sh`). The script starts a minimal HTTP health endpoint (so App Runner’s TCP checks pass without exposing source files) and then `exec`s the Celery worker. Give the worker the same IAM role permissions as the API (S3 read/write, SQS receive/delete, Secrets Manager for the bundle ARN).
- Smoke test: `python temp_scripts/test_artifact_upload.py --api-base-url https://api.jobapptracker.dev --token "$ACCESS_TOKEN" --file ~/Downloads/resume.pdf` creates/pins an artifact, uploads via the presigned URL, triggers background processing, and polls `GET /ai/artifacts/conversations/{id}` until it lands in `ready`/`failed`. Useful after each deploy to ensure the worker, SQS, and S3 wiring all function end-to-end.
- Frontend artifacts panel consumes the `/ai/artifacts` endpoints to show the resume/JD currently “in context,” display processing states (Pending / Ready / Failed with reason), and offer “Upload / Paste / Link” affordances for both roles.

### CI/CD pipelines

Production deploys are now automated through GitHub Actions:

- **Backend** — `.github/workflows/backend-deploy.yml`
  - Triggers on pushes to `main` that touch `backend/**`, the deploy script, or the workflow.
  - Uses GitHub OIDC to assume `AWS_ROLE_ARN_BACKEND`, builds the Docker image with `docker build` (linux/amd64), tags/pushes to ECR, then runs `scripts/deploy_apprunner.py` twice—first for the FastAPI API service, then for the Celery worker service. Set the following secrets: `APPRUNNER_SERVICE_ARN`, `BACKEND_HEALTH_URL`, `APPRUNNER_WORKER_SERVICE_ARN`, and the worker’s health URL (the worker exposes a simple 200 OK endpoint on `/`).
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

- Notable scripts:
  - `temp_scripts/env_to_json.py` – converts `.env` files into a JSON blob suitable for storing in AWS Secrets Manager (`python temp_scripts/env_to_json.py backend/.env > /tmp/backend-config.json`).
  - `temp_scripts/test_artifact_upload.py` – end-to-end artifact smoke test (`python temp_scripts/test_artifact_upload.py --api-base-url https://api.jobapptracker.dev --token "$ACCESS_TOKEN" --file ~/Downloads/resume.pdf`); confirms S3 upload, Celery processing, and `GET /ai/artifacts/conversations/{id}` all work in production.
  - `temp_scripts/reset_dev_db.py` – dev-only DB reset + S3 cleanup helper.

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

- Email verification is enforced by the app: after signup we route users to `/verify` to request/confirm a 6-digit code via Resend (`/auth/cognito/verification/send` + `/auth/cognito/verification/confirm`). If someone tries to log in before verifying, every protected API still returns `403 EMAIL_NOT_VERIFIED` and the UI redirects back to `/verify`. Once verified, the backend marks `users.is_email_verified = true` and syncs `email_verified=true` to Cognito via `AdminUpdateUserAttributes` so native clients stay in sync. Settings + flow docs live in `docs/architecture/cognito-option-b.md`.
- Idle timeout (frontend): `VITE_IDLE_TIMEOUT_MINUTES` (optional, default 30, minimum 5) controls how long the SPA waits before logging out an inactive tab.
- Idle timeout (frontend): `VITE_IDLE_TIMEOUT_MINUTES` (optional, default 30) controls how long the SPA waits before logging out a tab with no activity.

### AI context + summarization

- `AI_CONTEXT_TOKEN_BUDGET` – total tokens we aim to keep in the rolling context window; exposed via the context meter in `/ai/conversations`.
- `AI_SUMMARY_MESSAGE_THRESHOLD`, `AI_SUMMARY_TOKEN_THRESHOLD` – trigger conditions for automatic summaries (by message count and/or token total).
- `AI_SUMMARY_CHUNK_SIZE` – number of new messages fed into each summary update.
- `AI_SUMMARY_MAX_TOKENS`, `AI_SUMMARY_MODEL` – OpenAI parameters for the summarizer (falls back to `OPENAI_MODEL` if unset).

## Design Principles

- Small, reviewable changes
- Clear separation of concerns
- Explicit structure over hidden conventions
- AI-assisted development with human review and version-controlled memory