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
- Per-user UI preferences (e.g., collapsed cards) are persisted via `PATCH /users/me/ui-preferences` and hydrated through a shared `CurrentUserProvider`.
- `AuthProvider` centralizes Cognito token storage/logout and now enforces a client-side idle timeout (default ~30 minutes, configurable via `VITE_IDLE_TIMEOUT_MINUTES`, minimum 5). Mouse/keyboard/touch/scroll/visibility events reset the timer; idle tabs are logged out automatically.

### Backend (`backend/`)
- FastAPI + SQLAlchemy ORM + Alembic migrations on Postgres.
- Auth: Cognito Option B (Chunk 5‑7) with server-side JWKS verification. `/auth/cognito/*` handles signup/confirm/login/MFA/refresh/logout; tokens returned to the SPA are the raw Cognito tokens (stored client-side in memory + sessionStorage). Signup is gated by Cloudflare Turnstile (Chunk 8) and fails closed if CAPTCHA verification/configuration fails.
- AWS SDK: `boto3` (Cognito IdP, S3 uploads, GuardDuty callbacks).
- Tests: pytest.
- Password policy enforced via `app/core/password_policy.py` (length, upper/lowercase, number, special char, denylist, no name/email substrings).
- Users: `users` table stores `email`, `name`, `cognito_sub`, `auth_provider`, plus JSON `ui_preferences` for persisted UI state. Identity middleware JIT-provisions a row on first successful login and attaches it to every request.
- Database access split between least-privilege runtime (`DB_APP_USER`) and migrations (`DB_MIGRATOR_USER`) credentials.
- Production hosting: AWS App Runner pulling images from ECR, fronted by `https://api.jobapptracker.dev`; runtime secrets come from AWS Secrets Manager env injects. GitHub Actions (`backend-deploy.yml`) builds/pushes to ECR and drives App Runner updates via `scripts/deploy_apprunner.py`.
- Job detail hydration is consolidated behind `GET /jobs/{job_id}/details`, which returns `{job, notes, interviews, activity}` in one request so the Jobs page no longer issues four sequential calls on every selection. The legacy per-resource endpoints remain for incremental updates.

## AWS / External Services (current)
- **Email/Verification**: handled by Cognito (and future Cognito-triggered Lambda → Resend). No direct SMTP/SES integration in the FastAPI backend.
- **S3**: job document upload flow via presigned URLs (see `/jobs/{job_id}/documents/*`)
- **GuardDuty Malware Protection for S3**: AWS-managed malware scanning for uploaded documents. EventBridge triggers a Lambda forwarder, which updates the backend document `scan_status` by calling `/jobs/{job_id}/documents/{document_id}/scan-result` with a shared secret fetched from AWS Secrets Manager (Lambda stores only the secret ARN). The GuardDuty verdict is sourced from the S3 object tag `GuardDutyMalwareScanStatus` (Lambda falls back to S3 `GetObjectTagging` if the event payload does not include tags). GuardDuty callbacks are feature-gated via `GUARD_DUTY_ENABLED` so local Docker runs can noop safely.
- **App Runner**: hosts the backend container, pulls from ECR with `linux/amd64` images, injects env vars from Secrets Manager, handles health checks routed through `/health`.

## Cognito Auth (production state)
- SPA uses a custom UI (no Hosted UI redirect) backed by Option‑B API routes under `/auth/cognito/*`.
- Cognito verifier (`app/auth/cognito.py`) handles JWKS caching/rotation and enforces `token_use == "access"`, issuer, and client_id.
- `Identity` middleware verifies every request, attaches the DB user (JIT provisioning on first login), and exposes debug endpoints (`/auth/debug/token-info`, `/auth/debug/identity`) for local use.
- User model now contains only Cognito-backed fields (`email`, `name`, `cognito_sub`, `auth_provider`). Legacy password/verification columns were removed in the `cognito_cutover_cleanup` migration.
- Signup is protected by Cloudflare Turnstile (Chunk 8). `/auth/cognito/signup` requires `turnstile_token`; the backend posts tokens to Cloudflare’s `/siteverify`, fails closed if configuration is missing, and never logs secrets/tokens. CAPTCHA is enforced only on signup.
- Cognito handles reset emails via its default sender. Pre Sign-up Lambda auto-confirms users, while the backend now enforces verification via public endpoints (`/auth/cognito/verification/{send,confirm}`): signup redirects straight to `/verify`, users request/confirm 6-digit codes before their first login, and any user who does log in early is still blocked with `403 EMAIL_NOT_VERIFIED` until the flow completes. Codes are hashed (salted SHA-256), TTL/cooldown/attempt limits apply, Resend delivers the email, and we sync `email_verified=true` via `AdminUpdateUserAttributes`.
- Tokens:
  - Access/id tokens live in memory + `sessionStorage`.
  - Refresh tokens are stored in `sessionStorage` only; refreshes go through `/auth/cognito/refresh` (Cognito `REFRESH_TOKEN_AUTH`).
  - Logout clears the SPA session and best-effort calls `/auth/cognito/logout`.
- MFA (SOFTWARE_TOKEN_MFA) is enforced for every user. `/auth/cognito/mfa/setup` returns `SecretCode` + `otpauth://` for QR rendering; `/auth/cognito/mfa/verify` finalizes the login.
- Rate limiting applies to all `/auth/cognito/*` endpoints (SlowAPI). Enable `ENABLE_RATE_LIMITING` in prod and back it with Redis/Elasticache.
- Future enhancements: passkeys, native iOS auth flows, AI usage/billing attribution.
- **AI identity note**: `cognito_sub` remains the durable identifier for AI usage/billing features across clients.
- **Authorization**: All protected routes enforce user ownership using the DB `user.id` linked to `cognito_sub`.

## Intended Future Direction (high-level)
- iOS app (separate client, likely `frontend-ios/` when introduced)
- Deployment hardening: CI/CD now auto-deploys backend (App Runner) and frontend (S3 + CloudFront) on merge to `main` via `backend-deploy.yml` / `frontend-deploy.yml`; next steps include observability/alerts and staged environments.
- AI assistant features (resume/job-description tailoring, cover/thank-you letters with automatic S3 upload to a job record).
- Multi-factor authentication, passkey login, eventual biometric (Face ID) support on iOS — Cognito provides the foundation.
- Continued refactors: improve maintainability, reduce duplication, keep tests comprehensive

## Key Flows
### Auth (Cognito)
- `/register` → `/auth/cognito/signup` (payload now includes `turnstile_token`)
- `/verify` → `/auth/cognito/confirm`
- `/login` → `/auth/cognito/login` (may return `next_step`)
- `/mfa/setup` ↔ `/auth/cognito/mfa/setup` + `/auth/cognito/mfa/verify`
- `/mfa/code` ↔ `/auth/cognito/challenge` (SOFTWARE_TOKEN_MFA)
- `/auth/cognito/refresh` handles access-token rotation; SPA calls it automatically via `tokenManager`.

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


