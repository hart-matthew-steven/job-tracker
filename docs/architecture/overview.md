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
- Public marketing routes (`/` + `/demo/board`) showcase the product without hitting backend APIs; `/demo/board` renders a static, read-only board preview for prospects who have not created an account yet.
- Navigation shell keeps primary actions (global search, “Create job”) in the header for every breakpoint. On mobile the drawer is nav-only; keeping actions inline prevents workflow divergence between devices.

### Backend API (Python)
- Owns business logic and data persistence
- Exposes a REST API to the frontend
- Handles auth/session logic (if applicable)
- Integrates with AWS services for storage and background processing
- Coordinates file upload validation and anti-malware scanning

### Billing & AI Credits (Phase A)
- The backend now persists prepaid “AI Credits” in two tables: `credit_ledger` (balances) and `ai_usage` (future cost tracking). The DB remains the source of truth; nothing relies on Stripe or OpenAI yet.
- Credit balances are stored as integer cents. Doing all math in integers prevents float rounding drift and keeps idempotent reconciliations predictable when real money is involved.
- Every ledger row records `source` (`stripe`, `admin`, `promo`, `usage`, etc.) plus an optional `source_ref`. The `(user_id, source_ref)` pair is unique so future Stripe webhooks and admin tooling can retry safely without double-crediting.
- The upcoming AI usage features will populate `ai_usage.request_id` the same way for idempotency once OpenAI calls land. For now these tables are “write-once/read-later” foundations so accounting is ready when integrations ship.
- Stripe Checkout is the only way to purchase credits. Users are linked to Stripe customers (`users.stripe_customer_id`), and every purchase references a configured pack (`STRIPE_PRICE_MAP=pack:price_id:credits`). The backend accepts only a `pack_key`, resolves the Stripe price + credit quantity, and writes that metadata into the Checkout session so the webhook can’t be spoofed.
- Every webhook payload is written to `stripe_events` before any balance mutation. We track `status` (`pending`, `processed`, `skipped`, `failed`), the raw payload, and error text for observability/idempotency. A rerun that hits the `stripe_event_id` unique constraint simply returns `200 OK` without touching balances.
- Credits are minted exclusively by signed `checkout.session.completed` events where `payment_status=paid`. The handler runs inside a transaction: insert `stripe_events` → mint `credit_ledger` entry (with `pack_key`, checkout/payment intent ids, per-user `idempotency_key`) → mark status `processed|skipped`. Any exception sets `status=failed`, stores the error, and returns HTTP 500 so Stripe retries.
- Spending is also ledger-based: `spend_credits(user_id, amount, reason, idempotency_key)` locks the user row, recomputes the live balance, and inserts a negative row only when funds are available. If the balance would go negative we raise HTTP 402 and never touch the ledger. This ensures upcoming AI usage can’t accidentally “overspend” during concurrent requests.
- Stripe payment flows and OpenAI cost metering intentionally remain out of scope for Phase A—they will plug into this ledger/service layer later without reworking auth or migrations. When OpenAI usage ships, it will deduct from `credit_ledger` and write mirrored facts to `ai_usage`.

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

## File Scanning (AWS GuardDuty Malware Protection for S3)

Uploaded files are treated as untrusted input.

High-level approach:
- Files are not considered "accepted" or "safe" until scanned
- Scanning is performed by **AWS GuardDuty Malware Protection for S3** (AWS-managed service)
- A file that fails scanning is marked as INFECTED and download is blocked

Architecture:
- Files are uploaded to S3 via presigned URLs
- GuardDuty scans objects automatically (no file download by us)
- EventBridge forwards GuardDuty findings to a Lambda forwarder
- Lambda extracts `document_id` from S3 key and calls backend internal callback
- Backend updates DB `scan_status` (CLEAN/INFECTED/ERROR) and blocks downloads unless CLEAN

This project documents scanning behavior in more detail in:
- `docs/architecture/security.md`
- `docs/architecture/data-flow.md`

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