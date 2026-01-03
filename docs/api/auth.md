# API Authentication

This document describes authentication and authorization behavior for the Job Tracker API after the Cognito cutover (Chunks 5‑8).

---

## Authentication Model

Status: implemented (Cognito Option B / Backend-for-Frontend)

- `/auth/cognito/*` routes orchestrate Cognito SignUp/Confirm/Login/MFA/Refresh flows via the Cognito Identity Provider API. The frontend never talks to Cognito directly.
- Successful login/refresh responses return the raw Cognito tokens (`access_token`, `id_token`, `refresh_token`, `expires_in`, `token_type`). The SPA stores access/id tokens in memory + `sessionStorage`, refresh tokens in `sessionStorage` only.
- Every protected API request must include `Authorization: Bearer <Cognito access token>` (the only unauthenticated flows are signup/login/challenge/MFA and `/auth/cognito/verification/{send,confirm}`). `app/auth/cognito.py` validates signature, issuer, `token_use == "access"`, and `client_id`.
- Identity middleware (`app/middleware/identity.py`) attaches the DB user (JIT provisioning new users on first login). Authorization across the API is enforced against the DB user ID.
- Signup is guarded by **Cloudflare Turnstile**. `/auth/cognito/signup` requires `{email, password, name, turnstile_token}`; the backend verifies the token with Cloudflare’s `/siteverify` endpoint and fails closed if misconfigured.
- Email verification is now enforced by the Job Tracker backend (Chunk 11). Cognito accounts are auto-confirmed, but users cannot call protected APIs until they verify via `/auth/cognito/verification/{send,confirm}`. Once verified in our DB we sync `email_verified=true` to Cognito (`Username = cognito_sub`) for iOS parity.

---

## Authorization

Authorization rules are enforced on the backend service layer:

- All state-mutating endpoints require authentication.
- Access to resources is scoped to the owning user (`request.state.user` / `Identity`).
- Debug endpoints (`/auth/debug/*`) remain dev-only and are feature-gated.

---

## Headers

```
Authorization: Bearer <cognito-access-token>
```

Do not log token values. Structured logs should include only anonymized identifiers (e.g., Cognito `sub`).

---

## Token Handling

- **Signup**: `POST /auth/cognito/signup` with `{email, password, name, turnstile_token}`. Backend verifies Turnstile → `Cognito SignUp`.
- **Confirm (legacy Cognito)**: `POST /auth/cognito/confirm` with `{email, code}`. (Older fallback; primary flow uses the app-enforced endpoints below.)
- **Email verification (app-enforced)**:
  - `POST /auth/cognito/verification/send` — public, rate-limited endpoint; generates a 6-digit code, hashes it, emails via Resend.
  - `POST /auth/cognito/verification/confirm` — public endpoint; validates code, marks `users.is_email_verified` + `email_verified_at`, then calls Cognito `AdminUpdateUserAttributes` (`Username=cognito_sub`) to set `email_verified=true`.
- **Login**: `POST /auth/cognito/login` with `{email, password}`. Returns either `{status:"OK",tokens:{...}}` or `{status:"CHALLENGE",next_step,session}`.
- **Challenges**:
  - `/auth/cognito/mfa/setup` + `/auth/cognito/mfa/verify` (TOTP).
  - `/auth/cognito/challenge` (SOFTWARE_TOKEN_MFA, NEW_PASSWORD_REQUIRED, etc.).
- **Refresh**: `POST /auth/cognito/refresh` with `{refresh_token}` (Cognito `REFRESH_TOKEN_AUTH`).
- **Logout**: `POST /auth/cognito/logout` (best-effort API parity; clears SPA session).

The backend no longer issues bespoke JWTs or refresh cookies.

---

## Development vs Production

- **Development:** export `VITE_API_BASE_URL`, `VITE_TURNSTILE_SITE_KEY`, backend `COGNITO_*`, `TURNSTILE_*`, and the email verification env vars (`EMAIL_VERIFICATION_*`, `RESEND_*`, `FRONTEND_BASE_URL`) before running `npm run dev`. Cloudflare provides public Turnstile test keys for local use.
- **Production:** Secrets come from AWS Secrets Manager/App Runner configuration. Turnstile env vars must be set; missing keys block signup (fail closed). CORS origins must be explicit (no localhost).

---

## Updating this Document

Update this file when:
- the authentication mechanism changes (e.g., passkeys, hosted UI, additional CAPTCHA providers)
- token/session lifecycle changes
- authorization rules change