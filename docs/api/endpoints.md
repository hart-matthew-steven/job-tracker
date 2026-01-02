# API Endpoints

This is the endpoint inventory for the backend API.

Guidelines:
- Keep entries short and consistent.
- Include request/response examples only for stable endpoints.
- Prefer linking to schemas/types in code rather than duplicating large payloads.

---

## Health / Meta

- `GET /health`
  - Purpose: health check
  - Auth: none
  - Response: `{ "status": "ok" }` (example)

---

## Auth (`/auth/cognito/*`)

- `POST /auth/cognito/signup`
  - Auth: none
  - Body: `{ email, password, name, turnstile_token }`
  - Notes: backend verifies Cloudflare Turnstile token before calling Cognito `SignUp`

- `POST /auth/cognito/confirm`
  - Auth: none
  - Body: `{ email, code }`

- `POST /auth/cognito/login`
  - Auth: none
  - Body: `{ email, password }`
  - Notes: returns `{status:"OK",tokens:{...}}` on success or `{status:"CHALLENGE",next_step,session}` when Cognito requires MFA/setup

- `POST /auth/cognito/challenge`
  - Auth: none
  - Body: `{ email, challenge_name, session, responses }`
  - Notes: wraps Cognito `RespondToAuthChallenge` (e.g., SOFTWARE_TOKEN_MFA)

- `POST /auth/cognito/mfa/setup`
  - Auth: none
  - Body: `{ session, label? }`
  - Notes: calls Cognito `AssociateSoftwareToken`, returns `{secret_code, otpauth_uri, session}`

- `POST /auth/cognito/mfa/verify`
  - Auth: none
  - Body: `{ email, session, code, friendly_name? }`
  - Notes: calls `VerifySoftwareToken`, then `RespondToAuthChallenge` with `ANSWER=SUCCESS`

- `POST /auth/cognito/refresh`
  - Auth: none
  - Body: `{ refresh_token }`
  - Notes: proxies Cognito `REFRESH_TOKEN_AUTH`, returns updated tokens

- `POST /auth/cognito/logout`
  - Auth: Bearer (optional)
  - Notes: best-effort API parity—clears SPA session; no server-side refresh store exists

---

## Users

- `GET /users/me`
  - Auth: Bearer

- `POST /users/me/change-password`
  - Auth: Bearer
  - Notes: revokes refresh tokens on success

- `GET /users/me/settings`
  - Auth: Bearer

- `PUT /users/me/settings`
  - Auth: Bearer
  - Body: `{ "auto_refresh_seconds": 0|10|30|60 }`

---

## Jobs

- `GET /jobs`
  - Auth: Bearer

- `POST /jobs`
  - Auth: Bearer

- `GET /jobs/{job_id}`
  - Auth: Bearer

- `PATCH /jobs/{job_id}`
  - Auth: Bearer

## Notes

- `GET /jobs/{job_id}/notes`
  - Auth: Bearer

- `POST /jobs/{job_id}/notes`
  - Auth: Bearer

- `DELETE /jobs/{job_id}/notes/{note_id}`
  - Auth: Bearer

## Documents

- `GET /jobs/{job_id}/documents`
  - Auth: Bearer

- `POST /jobs/{job_id}/documents/presign-upload`
  - Auth: Bearer

- `POST /jobs/{job_id}/documents/confirm-upload`
  - Auth: Bearer

- `GET /jobs/{job_id}/documents/{doc_id}/presign-download`
  - Auth: Bearer

- `DELETE /jobs/{job_id}/documents/{doc_id}`
  - Auth: Bearer

---

## Updating this document

Update this file when:
- routes are added/removed/renamed
- request/response shapes change materially
- auth requirements change for an endpoint