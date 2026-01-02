# User Lifecycle

This document describes the user lifecycle in Job Tracker after the Cognito cutover (Chunk 7). All authentication is handled by Cognito access/refresh/id tokens; the backend no longer issues bespoke Job Tracker JWTs or refresh cookies.

## User States

| State | Description | Allowed Endpoints |
| --- | --- | --- |
| Unauthenticated | No valid Cognito session | `/health`, `/auth/cognito/*` |
| Authenticated (Cognito) | Bearer access token issued by Cognito | All protected routes |

There is **no** profile completion gate anymore. Every authenticated user (custom or Cognito) has a `users` row with a non-null `name`.

## Cognito lifecycle

1. **Sign up** (`POST /auth/cognito/signup`)
   - Body: `{email, password, name, turnstile_token}`
   - Backend enforces password policy and forwards to Cognito `SignUp`
   - Response: `status=CONFIRMATION_REQUIRED` (typical) or `status=OK`
2. **Confirm** (`POST /auth/cognito/confirm`)
   - Body: `{email, code}`
   - Calls Cognito `ConfirmSignUp`
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
5. **Refresh** (`POST /auth/cognito/refresh`)
   - Body: `{refresh_token}`
   - Runs Cognito `REFRESH_TOKEN_AUTH` and returns updated tokens.
6. **Logout** (`POST /auth/cognito/logout`): best-effort API parity (clears SPA session; no server-side refresh state exists).

- `/register` → wraps `/auth/cognito/signup`.
- `/verify` → wraps `/auth/cognito/confirm`.
- `/login` → orchestrates `/auth/cognito/login`, `/auth/cognito/mfa/setup`, `/auth/cognito/mfa/verify`, and `/auth/cognito/challenge`.
- `/mfa/setup` + `/mfa/code` → dedicated MFA screens.
- Logout clears the session from memory/sessionStorage and calls `/auth/cognito/logout` (best-effort).

## JIT Provisioning Rules

- `users` rows are created automatically when Cognito auth succeeds the first time.
- Fields populated: `email` (lowercased), `name` (required), `cognito_sub`, `auth_provider="cognito"`, `is_email_verified=True`.
- If a custom-auth user already exists with the same email, login fails with `409` until an explicit linking process is introduced (prevents accidental takeover).

## Token storage & refresh

- Access & ID tokens live in memory + sessionStorage. Refresh tokens are persisted in sessionStorage only.
- `tokenManager` refreshes ~60 s before expiry and deduplicates concurrent refreshes. Failures clear the session and force re-login.
- There is no legacy refresh-cookie state to revoke; Cognito’s refresh token TTL/rotation apply.

## MFA Notes

- Cognito User Pool enforces SOFTWARE_TOKEN_MFA (TOTP).
- `/auth/cognito/mfa/setup` returns `SecretCode` + `otpauth://` for QR rendering but never logs/persists the secret.
- `/auth/cognito/mfa/verify` finalizes setup and immediately completes the pending login.
