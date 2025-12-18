# Architecture Overview

This document describes the high-level architecture for Job Tracker, including component boundaries, AWS usage, development exposure via ngrok, and file-scanning via ClamAV.

The intent is to keep the root README concise while documenting real system shape and security posture here.

---

## Goals

- Clear separation between frontend, backend, documentation, logs, and one-off scripts
- Predictable, maintainable architecture that scales from local dev to AWS
- Secure file handling (untrusted uploads are scanned before acceptance/processing)
- Keep AI-assisted development deterministic (small scopes, versioned “memory” docs)

Non-goals:
- Document every AWS/IAM detail here (those belong in deeper, service-specific docs if needed)
- Over-abstract or “enterprise-ify” a personal project

---

## Components

### Frontend (React + Vite)
- Presents UI for job applications, statuses, notes, and related metadata
- Calls the backend via a centralized API client
- Runs locally in dev (`npm run dev`)
- Deployed separately from the backend in production (implementation can vary)

### Backend API (Python)
- Owns business logic and data persistence
- Exposes a REST API to the frontend
- Handles auth/session logic (if applicable)
- Integrates with AWS services for storage and background processing
- Coordinates file upload validation and anti-malware scanning

### AWS (Production Infrastructure)
The project assumes AWS-managed services are used for:
- Storage (e.g., uploads, generated artifacts)
- Persistence (DB choice can vary; architecture keeps it swappable)
- Background processing (queues/jobs/events)
- Observability/logging (as needed)

The exact services may evolve, but the architectural principle is stable:
- the backend remains the “control plane”
- AWS services are used for durability, security, and scalability

---

## Development vs Production

### Development
- Frontend runs locally on Vite’s dev server
- Backend runs locally (or in a local container)
- ngrok may be used to expose the backend temporarily for:
  - webhook testing
  - integration testing against external systems
  - mobile testing without local network configuration

Development principle:
- expose the minimum surface area needed
- keep secrets out of the repo
- keep logs and outputs in `logs/`

### Production
- Backend runs behind AWS-managed networking controls
- External access to backend is via a stable HTTPS endpoint
- Upload/storage/queues are AWS-managed for durability and security

Production principle:
- secure by default
- least privilege access to storage/queues
- scanned file workflow enforced

---

## File Scanning (ClamAV)

Uploaded files are treated as untrusted input.

High-level approach:
- Files are not considered “accepted” or “safe” until scanned
- Scanning is performed using ClamAV
- A file that fails scanning is quarantined/rejected and never processed further

Implementation options (architecture-compatible):
- Scan in a dedicated scanning service/container (recommended)
- Scan via a background job worker
- Scan before moving the file to its “final” storage location

This project documents scanning behavior in more detail in:
- `docs/architecture/security.md`

---

## Observability & Outputs

- Human-readable documentation belongs in `docs/`
- Script output and one-off run results belong in `logs/`
- Disposable scripts belong in `temp_scripts/`

If a log file is useful long-term:
- commit it intentionally
- treat it as an artifact, not canonical documentation

---

## AI-Assisted Development Conventions

This repo uses a versioned, explicit approach to AI context:
- Durable summaries go in `docs/ai/MEMORY.md`
- Decisions and rationale go in `docs/ai/DECISIONS.md`
- A repo map lives in `docs/ai/MAP.md`

This is intentional:
- it keeps costs predictable
- it avoids “mystery context”
- it makes work auditable and reproducible