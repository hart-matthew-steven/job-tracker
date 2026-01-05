# API Overview

This document describes the Job Tracker backend API at a consumer level:
- authentication (if enabled)
- common request/response conventions
- error format
- pagination/filtering (if enabled)
- where to find endpoint-specific details

For endpoint inventory and examples, see:
- `docs/api/endpoints.md`

---

## Base URL

Development:
- Backend runs locally (e.g., `http://localhost:<port>`)
- May be exposed via ngrok for webhook/integration testing (dev only)

Production:
- Served behind AWS-managed networking and HTTPS

---

## Authentication

- Mechanism: Cognito Option‑B (Backend-for-Frontend). Clients talk only to `/auth/cognito/*`; the backend calls Cognito IDP APIs on their behalf.
- Tokens: `/auth/cognito/login` returns the raw Cognito `access_token`, `id_token`, `refresh_token`, `expires_in`, `token_type`. SPAs store access/id tokens in memory + `sessionStorage` and refresh tokens in `sessionStorage` only.
- Headers: every protected endpoint requires `Authorization: Bearer <cognito-access-token>`.
- Email verification is enforced by the backend (`/auth/cognito/verification/{send,confirm}`) before other APIs can be used.
- CAPTCHA: `/auth/cognito/signup` requires a valid Cloudflare Turnstile token (`turnstile_token`), verified server-side.

Notes:
- Never document secret values. Reference env var names only.
- For flow specifics see `docs/api/auth.md`.

---

## Request/Response Conventions

### Content Types
- JSON request/response bodies unless explicitly noted.
- File uploads use multipart/form-data (if implemented).

### Common Headers
- `Content-Type: application/json` for JSON requests
- `Authorization: Bearer <token>` (if auth enabled)

### Resource IDs
- IDs are returned as strings unless otherwise specified.

---

## Error Format (recommended)

Errors should be consistent and actionable. Recommended structure:

- `error`: stable error code (string)
- `message`: user-readable message
- `details`: optional structured info for debugging

Example:

    {
      "error": "VALIDATION_ERROR",
      "message": "Invalid request payload",
      "details": { "field": "status" }
    }

---

## File Uploads (if enabled)

High-level expectations:
- Uploaded files are treated as untrusted until scanned.
- File status should be explicitly represented (PENDING_SCAN, CLEAN, REJECTED, etc.)
- Upload endpoints should return a stable file ID immediately and allow status polling.

For flow details, see:
- `docs/architecture/data-flow.md`
- `docs/architecture/security.md`

---

## Bundled responses

To keep the SPA snappy on high-latency networks, some routes intentionally return multiple resource types at once. The primary example is `GET /jobs/{job_id}/details`, which returns:

- `job`: `JobApplicationOut`
- `notes`: ordered newest → oldest
- `interviews`: user-scoped interview rows
- `activity`: timeline entries (default limit 20, clamp 1–200 via `activity_limit`)

The endpoint replaces four sequential requests on the Jobs page, but the underlying single-resource routes remain available for incremental updates (e.g., deleting a note still re-fetches `/jobs/{id}/notes` for truth).

---

## Updating this document

This file should be updated when:
- auth scheme changes
- response/error formats change
- cross-cutting API conventions change