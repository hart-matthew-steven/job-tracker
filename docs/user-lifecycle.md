# User Lifecycle

This document describes the user lifecycle in Job Tracker after the Cognito cutover (Chunk 7). All authentication is handled by Cognito access/refresh/id tokens; the backend no longer issues bespoke Job Tracker JWTs or refresh cookies.

## User States

| State | Description | Allowed Endpoints |
| --- | --- | --- |
| Unauthenticated | No valid Cognito session | `/health`, `/auth/cognito/*` (signup/login/challenge/MFA/etc.), `/auth/cognito/verification/send`, `/auth/cognito/verification/confirm` |
| Authenticated (email **not** verified) | Cognito access token issued, but `users.is_email_verified = false` | `/auth/cognito/verification/send`, `/auth/cognito/verification/confirm`, `/auth/cognito/logout`, `GET /users/me` |
| Authenticated (email verified) | Cognito access token + `users.is_email_verified = true` | All protected routes |

There is **no** profile completion gate anymore. Every authenticated user (custom or Cognito) has a `users` row with a non-null `name`.

## Cognito lifecycle

1. **Sign up** (`POST /auth/cognito/signup`)
   - Body: `{email, password, name, turnstile_token}`
   - Backend enforces password policy and forwards to Cognito `SignUp`
   - Response: `status=CONFIRMATION_REQUIRED` (typical) or `status=OK`
2. **Auto-confirm**
   - Cognito Pre Sign-up Lambda (`lambda/cognito_pre_signup/`) sets `autoConfirmUser=true` and `autoVerifyEmail=false`, so Cognito does **not** send its own confirmation emails. After signup the SPA routes directly to `/verify` to request the 6-digit code.
3. **Login** (`POST /auth/cognito/login`)
   - Body: `{email, password}`
   - On success: Cognito returns `{access_token,id_token,refresh_token,expires_in,token_type}`. Backend fetches profile attributes (`GetUser`) to JIT-provision `users.cognito_sub` and returns the Cognito tokens as-is.
   - On challenge: returns `{"status":"CHALLENGE","next_step":"MFA_SETUP|SOFTWARE_TOKEN_MFA|...","session":"..."}` so the client knows which endpoint to call next.
4. **Challenges**
   - `/auth/cognito/challenge`: Generic `RespondToAuthChallenge` wrapper (e.g., `SOFTWARE_TOKEN_MFA`). Example payload:
     ```json
     {
       "email": "dev@example.com",
       "challenge_name": "SOFTWARE_TOKEN_MFA",
       "session": "<session>",
       "responses": { "SOFTWARE_TOKEN_MFA_CODE": "123456" }
     }
     ```
   - `/auth/cognito/mfa/setup`: Calls `AssociateSoftwareToken` → returns `SecretCode` + `otpauth://` URI
   - `/auth/cognito/mfa/verify`: Calls `VerifySoftwareToken`, then `RespondToAuthChallenge` (`ANSWER=SUCCESS`) to finish login
4. **Email verification (app-enforced)**
   - `POST /auth/cognito/verification/send`: public endpoint that generates a 6-digit code, stores a salted hash + TTL/cooldown, and sends via Resend (response is generic so accounts can’t be enumerated).
   - `POST /auth/cognito/verification/confirm`: public endpoint that validates the hash/TTL/attempts, marks `users.is_email_verified = true`, sets `email_verified_at`, and calls Cognito `AdminUpdateUserAttributes` (`Username = cognito_sub`) with `email_verified=true`.
   - Recommended flow: signup → `/verify` (without logging in) → login → MFA. If someone logs in before verifying, identity middleware still returns `403 EMAIL_NOT_VERIFIED` for every protected API except the verification endpoints, logout, and `GET /users/me`.
5. **Refresh** (`POST /auth/cognito/refresh`)
   - Body: `{refresh_token}`
   - Runs Cognito `REFRESH_TOKEN_AUTH` and returns updated tokens.
6. **Logout** (`POST /auth/cognito/logout`): best-effort API parity (clears SPA session; no server-side refresh state exists).

- `/register` → wraps `/auth/cognito/signup`.
- `/verify` → screen (accessible with or without a Cognito session) that calls `/auth/cognito/verification/send` and `/auth/cognito/verification/confirm`.
- `/login` → orchestrates `/auth/cognito/login`, `/auth/cognito/mfa/setup`, and `/auth/cognito/mfa/verify`/`/auth/cognito/challenge`. After login the SPA auto-requests a verification code if needed and redirects to `/verify`.
- `/mfa/setup` + `/mfa/code` → dedicated MFA screens.
- Logout clears the session from memory/sessionStorage and calls `/auth/cognito/logout` (best-effort).

## JIT Provisioning Rules

- `users` rows are created automatically when Cognito auth succeeds the first time.
- Fields populated: `email` (lowercased), `name` (required), `cognito_sub`, `auth_provider="cognito"`, `is_email_verified=False`, `email_verified_at=NULL`. Verification flips the flag + timestamp and syncs Cognito.
- If a custom-auth user already exists with the same email, login fails with `409` until an explicit linking process is introduced (prevents accidental takeover).

## Token storage & refresh

- Access & ID tokens live in memory + sessionStorage. Refresh tokens are persisted in sessionStorage only.
- `tokenManager` refreshes ~60 s before expiry and deduplicates concurrent refreshes. Failures clear the session and force re-login.
- There is no legacy refresh-cookie state to revoke; Cognito’s refresh token TTL/rotation apply.

## MFA Notes

- Cognito User Pool enforces SOFTWARE_TOKEN_MFA (TOTP).
- `/auth/cognito/mfa/setup` returns `SecretCode` + `otpauth://` for QR rendering but never logs/persists the secret.
- `/auth/cognito/mfa/verify` finalizes setup and immediately completes the pending login.
