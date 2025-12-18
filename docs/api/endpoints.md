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

## Auth

- `POST /auth/register`
  - Auth: none
  - Notes: requires `name`, `email`, `password`; prints a verify link in dev

- `GET /auth/verify?token=...`
  - Auth: none
  - Notes: verifies email token

- `POST /auth/resend-verification`
  - Auth: none

- `POST /auth/login`
  - Auth: none
  - Notes: returns access token + sets HttpOnly refresh cookie

- `POST /auth/refresh`
  - Auth: refresh cookie
  - Notes: rotates refresh token; returns new access token

- `POST /auth/logout`
  - Auth: refresh cookie
  - Notes: revokes refresh token + clears cookie

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