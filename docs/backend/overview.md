# Backend Overview

This document describes the backend structure and conventions at a high level.

---

## Stack

- Python API (FastAPI-style architecture)
- Persistence: PostgreSQL + SQLAlchemy
- Background processing: AWS-managed (EventBridge, Lambda)
- File scanning: AWS GuardDuty Malware Protection for S3

---

## Responsibilities

- Owns business logic and persistence
- Provides a clean API contract to the frontend
- Handles uploads securely (scan-before-accept)
- Coordinates async jobs (scan, processing, analytics if added)

---

## Structure (fill in once confirmed)

Typical layout:
- `backend/app/main.py` — app entry point
- `backend/app/routes/` — HTTP routes
- `backend/app/services/` — business logic
- `backend/app/models/` — persistence models
- `backend/app/schemas/` — IO contracts
- `backend/app/core/` — config/auth/shared utilities

---

## Conventions

- Routes stay thin; services own logic
- Consistent error format
- Preserve API shapes during refactors unless intentionally versioned
- Treat uploads as hostile until scanned

---

## Email delivery (configuration)

The backend sends verification emails using the configured provider.

- **`EMAIL_PROVIDER`**: defaults to `resend` when unset.
  - Supported: `resend` (default), `ses`, `gmail`
  - Legacy alias: `smtp` is treated as `gmail`
- **`FROM_EMAIL`**: used only for `resend` and `ses` (do not use for `gmail`)
- **`RESEND_API_KEY`**: required when using `resend`
- **`AWS_REGION`**: used for AWS clients (including SES)

See `backend/.env.example` for the full list of backend variable names.

---

## Updating this document

Update when:
- folder structure changes
- auth/session model changes
- persistence approach changes
- background job architecture changes