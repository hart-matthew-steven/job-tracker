# API Authentication

This document describes authentication and authorization behavior for the Job Tracker API.

---

## Authentication Model

Status: implemented (access token + refresh cookie)

- Access token: `Authorization: Bearer <access_token>` (JWT)
- Refresh token: HttpOnly cookie (used only by `/auth/refresh` + `/auth/logout`)
- Email verification: required before login

---

## Authorization

Authorization rules should be enforced on the backend service layer.

General principles:
- All state-mutating endpoints require authentication
- Access to resources is scoped to the owning user
- Authorization checks are explicit and consistent

---

## Headers (if applicable)

Example header format:

    Authorization: Bearer <access-token>

Do not document actual token values.

---

## Token Handling (if applicable)

Lifecycle:
- `POST /auth/login` returns a short-lived access token and sets a refresh cookie.
- `POST /auth/refresh` rotates the refresh cookie and returns a new access token.
- `POST /auth/logout` revokes the refresh token (if present) and clears the cookie.

---

## Development vs Production

Development:
- Backend prints an email verification link on register/resend.
 - Email delivery is provider-configured via `EMAIL_PROVIDER` (defaults to `resend`). See `backend/.env.example` for backend variable names.

Production:
- Auth is required and enforced
- No dev-only shortcuts
- Secrets managed outside the repo

---

## Updating this Document

Update this file when:
- authentication mechanism changes
- token/session lifecycle changes
- authorization rules change