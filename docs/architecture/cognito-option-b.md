# Cognito Option B (Backend-for-Frontend)

## Why Option B?
- Keep the SPA and future iOS app talking to **one backend**; Cognito never issues tokens directly to clients during the flow.
- Allow us to control the migration path: initial chunks mirrored the legacy session contract, and Chunk 7 switched clients to raw Cognito tokens without changing the external API surface.
- Enable consistent audit/logging and future AI/billing attribution keyed by `users.cognito_sub`.
- Centralise MFA handling (TOTP) so UX is identical across web/iOS and security decisions remain server-side.

## Response contract (Chunk 6)

- `CognitoAuthResponse.status` is `OK` or `CHALLENGE`.
- `next_step` normalises Cognito’s `ChallengeName` so the frontend can branch:
  - `MFA_SETUP`
  - `SOFTWARE_TOKEN_MFA`
  - `NEW_PASSWORD_REQUIRED`
  - `CUSTOM_CHALLENGE`
  - `UNKNOWN`
- Every challenge response includes the latest Cognito `session` (required when calling `/auth/cognito/challenge` or `/auth/cognito/mfa/*`).
- Successful responses (`status=OK`) include the raw Cognito tokens (`access_token`, `id_token`, `refresh_token`, `expires_in`, `token_type`). The backend no longer mints a separate Job Tracker JWT or refresh cookie.

## Request Flow (text sequence)

1. **Signup**
   - Frontend calls `POST /auth/cognito/signup` with `{email, password, name, turnstile_token}`. The backend verifies the Turnstile token before calling Cognito `SignUp`.
   - Backend enforces password policy, calls `Cognito SignUp`, and returns `status=CONFIRMATION_REQUIRED` if Cognito needs email confirmation.
2. **Confirmation**
   - `POST /auth/cognito/confirm` with `{email, code}` calls `ConfirmSignUp`.
3. **Login**
   - `POST /auth/cognito/login` calls `InitiateAuth`.
   - On success (`AuthenticationResult`):
     - Backend calls `GetUser` with the Cognito AccessToken, extracts `{sub,email,name}`.
     - `ensure_cognito_user()` JIT-provisions `users.cognito_sub` + `users.name`.
    - Backend returns the Cognito tokens as-is (no Job Tracker refresh cookie) and responds with `{"status":"OK","tokens":{...}}`.
   - On challenge (`ChallengeName` present):
     - Backend returns `{"status":"CHALLENGE","next_step":"MFA_SETUP|SOFTWARE_TOKEN_MFA|...","session":"..."}` so the SPA can drive the next step via `/auth/cognito/challenge` or `/auth/cognito/mfa/*`.
4. **MFA (TOTP)**
   - `MFA_SETUP` → `/auth/cognito/mfa/setup` → Cognito `AssociateSoftwareToken` → returns `SecretCode` + `otpauth://` URI.
   - User scans QR code.
   - `/auth/cognito/mfa/verify` calls `VerifySoftwareToken` then `RespondToAuthChallenge` to finish login.
   - `SOFTWARE_TOKEN_MFA` → `/auth/cognito/challenge` with the TOTP code; backend responds to challenge on behalf of the client.
5. **Logout**
   - `/auth/cognito/logout` exists for API parity; the SPA clears its stored tokens and calls the endpoint as a best-effort action.

## Frontend integration (Chunk 7)

- `src/api/authCognito.ts` mirrors the backend endpoints; requests include `credentials: "include"` for parity but tokens/refresh state now live entirely in memory + sessionStorage.
- `AuthProvider` stores the Job Tracker access token in `sessionStorage` (broadcasting changes via localStorage) and exposes `logout()` which calls `/auth/cognito/logout` before clearing storage.
- React Router routes:
  - `/register` → signup
  - `/verify` → email code confirmation
  - `/login` → handles `status=OK` vs `status=CHALLENGE`
  - `/mfa/setup` → scans QR + verifies via `/auth/cognito/mfa/*`
  - `/mfa/code` → responds to SOFTWARE_TOKEN_MFA challenges
- Frontend tests cover: login success, both challenge branches, MFA setup/verify flows, and logout clearing auth state.

## Security Model

- **Backend verifies tokens**: Cognito access/refresh tokens are returned to the SPA, but the backend enforces issuer/client/`token_use` on every request.
- **Rate limiting**: The SPA cannot brute-force Cognito directly; API Gateway controls apply immediately.
- **Name is mandatory**: `users.name` is NOT NULL, enforced at signup (both custom and Cognito flows).
- **JIT provisioning**: `ensure_cognito_user` creates a user if `cognito_sub` not known; rejects silent linking if an email already exists.
- **MFA**: Because Cognito is configured for required TOTP, every login flows through the backend challenge contract. The SPA never needs AWS credentials or to know Cognito challenge semantics.
- **Pre Sign-up Lambda (Chunk 10)**: `lambda/cognito_pre_signup/` is wired to the Cognito Pre Sign-up trigger. It sets `event.response.autoConfirmUser = true` and `event.response.autoVerifyEmail = false`, performs no network calls, and simply logs the trigger source. This prevents Cognito from emailing codes while keeping accounts in `CONFIRMED` state immediately, so our application logic decides when to send verification mail.
- **App-enforced email verification (Chunk 11)**: `/auth/cognito/verification/send` + `/auth/cognito/verification/confirm` are public so users can verify before their first login. The backend generates 6-digit codes, stores only salted SHA-256 hashes with TTL/cooldown/attempt caps, delivers via Resend, and on success sets `users.is_email_verified = true`, `users.email_verified_at`, and calls `AdminUpdateUserAttributes` (`Username=cognito_sub`, `email_verified=true`) to keep Cognito/iOS clients consistent.

## Email Verification Flow (detailed)

1. **Signup**
   - `/auth/cognito/signup` receives `{email,password,name,turnstile_token}`.
   - Backend verifies the Turnstile token, enforces password policy, and forwards to Cognito `SignUp`.
   - Pre Sign-up Lambda auto-confirms users and suppresses Cognito’s built-in email.
   - When email verification is enabled, the backend immediately creates a verification code and sends it via Resend so the UI can route to `/verify`.

2. **Request code (`/auth/cognito/verification/send`)**
   - Public, rate-limited endpoint (email only).
   - Generates a 6-digit code, stores `{code_hash, code_salt, expires_at, resend_available_at, attempts}` in `email_verification_codes`.
   - Enforces one active code per user; previous codes are invalidated on resend.
   - Returns a generic success response with `resend_available_in_seconds` to drive the UI cooldown, without leaking whether the email exists.

3. **Confirm code (`/auth/cognito/verification/confirm`)**
   - Public endpoint (no auth required).
   - Validates hash/TTL/attempts. On success:
     - Marks the DB user verified (`is_email_verified=True`, `email_verified_at=now()`).
     - Calls `cognito_admin_mark_email_verified` → Cognito `AdminUpdateUserAttributes` (`Username=cognito_sub`, `email_verified=true`).
     - Consumes the code so reuse fails.
   - Failures increment `attempts` and return safe error codes.

4. **Middleware enforcement**
   - Identity middleware allows only verification endpoints, logout, and `GET /users/me` until the DB flag is true.
   - Any 403 with `EMAIL_NOT_VERIFIED` triggers a frontend redirect back to `/verify`.

5. **Future clients**
   - Because Cognito receives `email_verified=true`, native clients can rely on the Cognito attribute without additional API calls.
   - Resend delivery + hashed storage ensures verification remains auditable and GDPR/AI-billing friendly.

## Files

- `app/routes/auth_cognito.py` — Signup/login/challenge/MFA/logout endpoints.
- `app/services/cognito_client.py` — boto3 wrapper that translates AWS exceptions into typed errors.
- `app/services/users.py` — JIT provisioning + name normalization.
- `backend/tests/test_auth_cognito_bff.py` — unit tests covering success, challenge, and MFA setup/verify paths.


