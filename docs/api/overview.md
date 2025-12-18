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

## Authentication (if applicable)

- Auth mechanism: (TBD / document once implemented)
- Session/token handling: (TBD)
- Authorization rules: (TBD)

Notes:
- Do not document secret values here.
- Document header names and flows only.

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

## Updating this document

This file should be updated when:
- auth scheme changes
- response/error formats change
- cross-cutting API conventions change