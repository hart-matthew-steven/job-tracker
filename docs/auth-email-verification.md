# App-Enforced Email Verification

Status: Implemented in **Chunk 11**.

## Why move verification out of Cognito?

- Cognito’s confirmation codes were disabled when we introduced the Pre Sign-up Lambda (Chunk 10). Users were auto-confirmed but Cognito still believed emails might be unverified.
- We need a consistent verification experience across web + future iOS clients, with Resend as the delivery provider.
- Verification status must live in our database (for AI billing/auditing) and reflect back to Cognito so native clients see `email_verified = true`.

## Flow Overview

1. **Signup:** User completes `/auth/cognito/signup` (Turnstile-protected). Cognito auto-confirms via the Pre Sign-up Lambda.
2. **Verification prompt (before login):** The frontend routes directly to `/verify?email=...` so the user can enter the code without logging in first.
3. **Request code:** `POST /auth/cognito/verification/send`
   - When signup succeeds with email verification enabled, the backend automatically creates the first code and sends it via Resend. The verification page shows “code sent” and honors the cooldown before letting the user resend.
   - Manual requests hit this public, rate-limited endpoint (email only). It generates a 6-digit numeric code, stores only a salted hash, enforces TTL + resend cooldown + attempt limits, and responds generically to avoid leaking whether the email exists.
4. **Confirm code:** `POST /auth/cognito/verification/confirm`
   - No auth required; validates hash, TTL, attempts.
   - Marks `users.is_email_verified = true`, `users.email_verified_at = now()`.
   - Calls Cognito `AdminUpdateUserAttributes` with `Username = cognito_sub` to set `email_verified=true`.
5. **Login/MFA:** After verification, the user signs in (and, if required, completes MFA). Middleware still blocks any unverified login attempts with `403 EMAIL_NOT_VERIFIED`, so stragglers are redirected back to `/verify`.

### Sequence (text)

```
User → /auth/cognito/login
Backend → Cognito USER_PASSWORD_AUTH (OK) → returns tokens
User → /auth/cognito/verification/send
Backend:
  - ensure cooldown
  - hash/store code
  - Resend email (no code logged)
User → /auth/cognito/verification/confirm (email + code)
Backend:
  - validate hash/TTL/attempts
  - admin_update_user_attributes (Username = cognito_sub, email_verified=true)
  - set users.is_email_verified = true, email_verified_at = now()
User → API (jobs etc.) → allowed
```

## Security Notes

- Codes are 6-digit numeric strings, hashed with a per-code salt (SHA-256).
- Only one active code per user; previous codes are invalidated on resend.
- Configurable TTL (default 15 minutes), resend cooldown (default 60s), attempt cap (default 10). Values live in ENV.
- Resend integration uses the official Python SDK; API keys + from-address are provided via env vars.
- Middleware blocks all protected endpoints with `403 EMAIL_NOT_VERIFIED` until the DB flag is true. Whitelisted paths: verification endpoints, logout, `GET /users/me`.
- Cognito sync is treated as transactional: if `AdminUpdateUserAttributes` fails, the DB update is rolled back and the user remains unverified.

## Operational Notes

- Feature toggle: `EMAIL_VERIFICATION_ENABLED`. Keep `false` for smoke tests; prod must set to `true`.
- ENV summary:
  - `EMAIL_VERIFICATION_CODE_TTL_SECONDS` (default 900)
  - `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` (default 60)
  - `EMAIL_VERIFICATION_MAX_ATTEMPTS` (default 10)
  - `RESEND_API_KEY`, `RESEND_FROM_EMAIL`
  - `FRONTEND_BASE_URL` (used in future emails)
- Logs never include the raw code; only delivery events and anonymized user IDs.
- Future Resend-based flows (passwordless login, welcome journeys) can reuse the same client module.

## Local Testing

1. Set env vars from `.env.example` (Resend API key + from email can be mocked in dev).
2. Run backend + frontend normally.
3. Signup → login → expect 403 when hitting `/jobs`.
4. Call `/auth/cognito/verification/send` (curl or via UI). No token required in dev since the endpoint is public; prod rate limits still apply.
5. Use DB/log output (dev mode) to obtain the code or wire a fake Resend key that simply logs the payload.
6. Confirm via `/auth/cognito/verification/confirm` → app access restored.


