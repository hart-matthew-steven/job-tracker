# Data Flow

This document describes how data moves through the system. It is written to be implementation-flexible (you can swap specific AWS services later) while keeping workflow and security properties stable.

---

## Legend

    [FE]   Frontend (React + Vite)
    [API]  Backend API (Python)
    [AWS]  AWS-managed services (storage/queue/db)
    [AV]   ClamAV scanning service/worker
    [DB]   Persistence layer (DB)

---

## High-Level System View

    User
      |
      v
    [FE]  --->  [API]  --->  [DB]
                 |
                 +----> [AWS Storage / Queue / Jobs]
                           |
                           v
                         [AV]
                           |
                           v
                         [DB] (status updates)

---

## 1) User loads the app

    User
      |
      v
    [FE] --(GET /session, GET /apps, etc)--> [API] --> [DB]
      |
      v
    Renders UI

Key properties:
- Backend is the source of truth.
- Frontend remains thin and presentation-focused.

---

## 2) Create or update a job application

    [FE] --(POST/PUT /applications)--> [API] --> [DB]
     ^                                  |
     |                                  v
     +-----------(JSON response)--------+

Optional (future):
    [API] --> [AWS Queue/Event] --> worker --> [DB] (analytics/audit)

---

## 3) Upload a document (resume, cover letter, etc.)

### States (recommended)
    PENDING_SCAN -> SCANNING -> CLEAN
                       |
                       +-> REJECTED
                       |
                       +-> FAILED (retryable)

### Flow (staged upload + scan)

    [FE] --(upload request)--> [API]
      |
      | (upload file)
      v
    [AWS Storage: STAGING]  (untrusted)
      |
      v
    [API] records metadata in [DB] with state = PENDING_SCAN
      |
      v
    [API] enqueues scan job/event --------------+
      |                                        |
      v                                        v
    [AWS Queue/Jobs] -----------------------> [AV]
                                              |
                                              | (download/read staged file)
                                              v
                                       scan with ClamAV
                                              |
                    +-------------------------+-------------------------+
                    |                                                   |
                    v                                                   v
                 CLEAN                                                REJECTED/FAILED
                    |                                                   |
                    v                                                   v
    promote to [AWS Storage: CLEAN] OR mark clean in [DB]      quarantine/delete + update [DB]
                    |
                    v
        [FE] can now access/attach the file safely

Security properties:
- Untrusted files stay in STAGING until scanned.
- Only CLEAN files are promoted/usable.
- Failures never “partially succeed.”

---

## 4) Background processing (async jobs)

General pattern:

    [API] --> [AWS Queue/Jobs] --> worker --> [DB]
                         |
                         v
                      retries + DLQ (optional)

Reliability properties:
- Jobs should be idempotent where possible.
- Failures tracked and retryable.
- Status written to DB in a consistent format.

---

## Dev vs Prod Differences

### Development (ngrok)
Only ingress changes:

    Internet --> ngrok --> [API(local)] --> [DB(local or dev)]
                                   |
                                   v
                              [AWS(dev)] (optional)

Rules:
- Keep ngrok short-lived.
- Do not bypass scan flow for convenience.
- Do not leak tokens/URLs into logs or commits.

### Production (AWS)
Stable ingress + hardened controls:

    Internet --> [AWS Ingress] --> [API] --> [DB]
                          |
                          v
                     [AWS Storage/Queue] --> [AV] --> [DB]

---

## Error & Status Contract (recommended)

For any file upload:
- return a stable ID immediately
- expose a status endpoint or include status in normal reads
- statuses:
  - PENDING_SCAN
  - SCANNING
  - CLEAN
  - REJECTED
  - FAILED

Frontend:
- show progress/state
- display actionable errors
- allow retry when policy allows

---

## Outputs & Artifacts

- Store run outputs under `logs/` (ignored by default in git).
- Summarize key takeaways in `docs/ai/MEMORY.md`.
- Record architectural/security decisions in `docs/ai/DECISIONS.md`.