# Job Tracker

A personal job application tracking system with a React (Vite) frontend and a Python backend API.

This repository is intentionally structured to keep source code, documentation, execution output, and one-off scripts clearly separated. The goal is to make the project easy to understand, maintain, and extend—both for personal use and for external reviewers.

---

## Repository Structure

    job-tracker/
    ├── frontend-web/        # React + Vite application
    ├── backend/             # Python API
    ├── docs/                # Project documentation (including AI-generated summaries)
    ├── logs/                # Script output and run results (not source-of-truth)
    ├── temp_scripts/        # One-off or exploratory scripts (disposable by default)
    └── .cursor/             # Cursor rules and AI behavior configuration

---

## High-Level Architecture

At a high level, the system consists of:

- A React frontend for user interaction
- A Python backend API for business logic and persistence
- AWS-managed infrastructure for storage, background processing, and security controls
- Supporting services for file scanning and operational safety

Development vs Production:
- **Development:** the backend API may be exposed via ngrok to support local development, webhooks, and external integrations
- **Production:** the backend runs behind AWS-managed networking and security controls

Security considerations:
- Uploaded files are scanned using ClamAV before being accepted or processed
- File handling and scanning behavior is designed to minimize risk and isolate untrusted input

Detailed architecture diagrams and data-flow documentation live under:
- `docs/architecture/overview.md`
- `docs/architecture/data-flow.md`
- `docs/architecture/security.md`

---

## Frontend

Location: `frontend-web/`  
Stack: React + Vite (JavaScript)

Responsibilities:
- User interface for tracking job applications and statuses
- Views for notes, documents, and related metadata
- Communication with the backend via a centralized API client

Common entry points:
- `frontend-web/src/main.jsx`
- `frontend-web/src/App.jsx`

Frontend-specific documentation (if present) lives under:
- `docs/frontend/`

---

## Backend

Location: `backend/`  
Stack: Python API (FastAPI-style architecture)

Responsibilities:
- Authentication and session handling (if applicable)
- API endpoints for job applications, notes, and related resources
- Data validation, persistence, and error handling
- Integration with background processing and security services

Typical structure:

    backend/app/
    ├── routes/      # HTTP route definitions
    ├── services/    # Business logic
    ├── models/      # Database models
    ├── schemas/     # Request/response schemas
    ├── core/        # Configuration, auth, and shared utilities

Backend-specific documentation (if present) lives under:
- `docs/backend/`

---

## Documentation

All project documentation lives under the `docs/` directory.

AI-assisted development is supported via a small set of version-controlled files:
- `docs/ai/MEMORY.md` — rolling summary of current project state and recent work
- `docs/ai/DECISIONS.md` — ADR-lite decision log (what was chosen and why)
- `docs/ai/MAP.md` — high-level map of key folders and entry points

These files are intentionally concise and updated incrementally as the project evolves.

---

## Logs

The `logs/` directory contains output from script executions, refactor runs, and other non-authoritative artifacts.

Rules:
- Logs are ignored by default in Git
- Logs are not source-of-truth documentation
- Any log worth keeping should be committed intentionally

---

## Temporary Scripts

The `temp_scripts/` directory is reserved for one-off or exploratory scripts such as:
- data migrations
- investigations
- refactor support utilities

Rules:
- Scripts here are disposable by default
- They should not be imported by production code
- If a script becomes permanent, it should be moved into an appropriate source directory

---

## Development (High-Level)

Frontend:

    cd frontend-web
    npm install
    npm run dev

Backend:

    cd backend
    # create virtual environment
    # install dependencies
    # run the API

See `docs/` for deeper or component-specific documentation as the project evolves.

---

## Design Principles

- Small, reviewable changes
- Clear separation of concerns
- Explicit structure over hidden conventions
- AI-assisted development with human review and version-controlled memory