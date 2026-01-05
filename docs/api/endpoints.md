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

- `POST /auth/cognito/verification/send`
  - Auth: none (rate-limited; responds generically)
  - Body: `{ email }`
  - Notes: generates a 6-digit code, stores a salted hash, enforces TTL/cooldown, and emails the code via Resend.

- `POST /auth/cognito/verification/confirm`
  - Auth: none
  - Body: `{ email, code }`
  - Notes: validates code hash/TTL/attempts, sets `users.is_email_verified=true`, syncs `email_verified=true` back to Cognito (`Username=cognito_sub`).

- `POST /auth/cognito/logout`
  - Auth: Bearer (optional)
  - Notes: best-effort API parity—clears SPA session; no server-side refresh store exists

---

## Users

- `GET /users/me`
  - Auth: Bearer
  - Response: includes `ui_preferences` JSON for persisted UI state (collapsed cards, etc.)

- `POST /users/me/change-password`
  - Auth: Bearer
  - Notes: revokes refresh tokens on success

- `GET /users/me/settings`
  - Auth: Bearer

- `PUT /users/me/settings`
  - Auth: Bearer
  - Body: `{ "auto_refresh_seconds": 0|10|30|60 }`

- `PATCH /users/me/ui-preferences`
  - Auth: Bearer
  - Body: `{ "preferences": { "job_details_notes_collapsed": true } }`
  - Notes: persists SPA/UI toggles (e.g., collapsed panels) across devices.

---

## Jobs

- `GET /jobs`
  - Auth: Bearer
  - Notes: Supports `q`, `status[]`, `tag[]`, `tag_q` filters.

- `POST /jobs`
  - Auth: Bearer
  - Body: `JobApplicationCreate`

- `GET /jobs/{job_id}`
  - Auth: Bearer

- `GET /jobs/{job_id}/details`
  - Auth: Bearer
  - Query: `activity_limit` (default 20, 1–200)
  - Notes: Returns `{ job, notes, interviews, activity: { items, next_cursor } }` so the Jobs page can hydrate in one request. Use `next_cursor` to fetch additional activity via `/jobs/{job_id}/activity`.

- `PATCH /jobs/{job_id}`
  - Auth: Bearer
  - Body: `JobApplicationUpdate`
  - Notes: Tag/status changes log activity entries.

### Activity

- `GET /jobs/{job_id}/activity`
  - Auth: Bearer
  - Query:
    - `limit` (default 20, 1–200)
    - `cursor_id` (optional) — fetch entries older than the given activity id
  - Response: `{ items: JobActivity[], next_cursor: number | null }`. Continue requesting with `cursor_id = next_cursor` until it returns `null`.

### Notes

- `GET /jobs/{job_id}/notes`
  - Auth: Bearer

- `POST /jobs/{job_id}/notes`
  - Auth: Bearer

- `DELETE /jobs/{job_id}/notes/{note_id}`
  - Auth: Bearer

### Interviews

- `GET /jobs/{job_id}/interviews`
  - Auth: Bearer

- `POST /jobs/{job_id}/interviews`
  - Auth: Bearer
  - Body: `JobInterviewCreate`

- `PATCH /jobs/{job_id}/interviews/{interview_id}`
  - Auth: Bearer
  - Body: `JobInterviewUpdate`

- `DELETE /jobs/{job_id}/interviews/{interview_id}`
  - Auth: Bearer

### Documents

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

- `POST /jobs/{job_id}/documents/{document_id}/scan-result`
  - Auth: Shared secret (`X-Scan-Secret`)
  - Notes: GuardDuty → backend scan callback path.

## Saved Views

- `GET /saved-views`
  - Auth: Bearer

- `POST /saved-views`
  - Auth: Bearer
  - Body: `SavedViewCreate`

- `PATCH /saved-views/{view_id}`
  - Auth: Bearer
  - Body: `SavedViewUpdate`

- `DELETE /saved-views/{view_id}`
  - Auth: Bearer

## Internal (GuardDuty/Lambda)

- `GET /internal/documents/{doc_id}`
  - Auth: Shared secret header (`X-Doc-Scan-Secret` preferred)
  - Notes: Debug helper to inspect scan status when GuardDuty is enabled.

- `POST /internal/documents/{doc_id}/scan-result`
  - Auth: Shared secret header
  - Notes: Legacy callback path; GuardDuty forwarder now uses `/jobs/{job_id}/documents/{document_id}/scan-result`.

---

## Updating this document

Update this file when:
- routes are added/removed/renamed
- request/response shapes change materially
- auth requirements change for an endpoint