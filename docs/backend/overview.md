# Backend Overview

This document describes the backend structure and conventions at a high level.

---

## Stack

- Python API (FastAPI-style architecture)
- Persistence: (TBD)
- Background processing: (TBD)
- File scanning: ClamAV

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

## Updating this document

Update when:
- folder structure changes
- auth/session model changes
- persistence approach changes
- background job architecture changes