# Data Flow

This document describes how data moves through the system. It is written to be implementation-flexible (you can swap specific AWS services later) while keeping workflow and security properties stable.

---

## Legend

    [FE]   Frontend (React + Vite)
    [API]  Backend API (Python)
    [AWS]  AWS-managed services (storage/queue/db)
    [GD]   AWS GuardDuty Malware Protection for S3
    [DB]   Persistence layer (DB)

---

## High-Level System View

    User
      |
      v
    [FE]  --->  [API]  --->  [DB]
                 |
                 +----> [AWS S3]
                           |
                           v
                         [GD] (GuardDuty scans object)
                           |
                           v
                      [EventBridge]
                           |
                           v
                     [Lambda forwarder]
                           |
                           v
                         [API] --> [DB] (status updates)

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

## 2.5) Load a job’s full detail view (bundled endpoint)

    [FE] --(GET /jobs/{job_id}/details?activity_limit=20)--> [API] --> [DB]
      ^                                                         |
      |                                                         +--> notes (ordered newest→oldest)
      |                                                         +--> interviews (user-scoped)
      |                                                         +--> job activity (limited slice)
      +----------------(single JSON payload with {job,notes,interviews,activity})---------------+

Why: JobsPage used to fire four sequential requests (`GET /jobs/{id}`, `/notes`, `/interviews`, `/activity`). The new endpoint returns the entire bundle in one round trip so the UI hydrates immediately and latency stays low even on high-RTT networks. The `activity_limit` query param defaults to 20 (min 1, max 200) so the frontend can request a smaller slice when needed.

---

## 3) Upload a document (resume, cover letter, etc.)

### States (implemented)

There are two related fields:
- DB `scan_status`: `PENDING` → `CLEAN` | `INFECTED` | `ERROR`
- UI `status` (legacy UI lifecycle): `pending` → `scanning` → `uploaded` | `infected` | `failed`

### Flow (S3 → GuardDuty → EventBridge → Lambda → Backend callback)

    User
      |
      v
    [FE] POST /jobs/{id}/documents/presign-upload  --------------------+
      |                                                                |
      |  (DB row created; scan_status=PENDING; status=pending)          |
      |                                                                |
      +--> PUT presigned S3 URL (<=5MB) --> [AWS S3] (untrusted object) |
                                                                   +---+
                                                                   |
    [FE] POST /jobs/{id}/documents/confirm-upload  -----------------+
      |   (status=scanning; still scan_status=PENDING)
      |
      v
    [AWS S3] object uploaded
      |
      v
    [GuardDuty Malware Protection for S3] scans object (no file download by us)
      |
      v
    [EventBridge] receives GuardDuty scan completion event
      |
      v
    [Lambda: guardduty_scan_forwarder]
      |
      | extracts document_id + job_id from S3 key
      | verdict source of truth: S3 object tag GuardDutyMalwareScanStatus
      | (if verdict not in event, Lambda calls S3 GetObjectTagging)
      | maps verdict -> CLEAN/INFECTED/ERROR
      |
      +--> NO_THREATS_FOUND -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
      |                         updates scan_status=CLEAN; status=uploaded
      |
      +--> THREATS_FOUND    -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
      |                         updates scan_status=INFECTED; status=infected
      |
      +--> ERROR/UNKNOWN    -> POST /jobs/{job_id}/documents/{document_id}/scan-result (X-Scan-Secret)
                               updates scan_status=ERROR; status=failed
      |
      | (Legacy internal endpoint `/internal/documents/{document_id}/scan-result` remains for manual/debug callbacks)

Security properties:
- Files are treated as hostile until scan_status == CLEAN.
- Backend blocks downloads unless scan_status == CLEAN.
- GuardDuty handles scanning without us downloading or processing untrusted files.
- Infected files remain in S3 but are marked as INFECTED in DB (download blocked).

### Dev note (current)

- In production the Lambda calls the App Runner API directly (e.g., `https://api.jobapptracker.dev/jobs/.../scan-result`).
- For local testing you can still point the Lambda at an ngrok tunnel, but production traffic no longer relies on ngrok.

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
                     [AWS S3] --> [GD] --> [EventBridge] --> [Lambda forwarder] --> [API] --> [DB]

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