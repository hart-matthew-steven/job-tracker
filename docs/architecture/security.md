# Security Architecture

This document describes the security posture of Job Tracker, with emphasis on:
- safe handling of untrusted uploads
- development vs production exposure (ngrok vs AWS)
- least-privilege access patterns
- logging and data hygiene

This is a living document; keep it accurate, concise, and implementation-aligned.

---

## Threat Model (Practical)

Primary risks we design for:
- Malicious file uploads (malware, exploits in document parsers)
- Accidental exposure of a development API to the internet
- Secret leakage (logs, commits, screenshots, copied config)
- Over-privileged access to storage/queues (blast radius too large)
- Data integrity issues (tampering, partial updates)

Non-goals:
- Defending against a nation-state adversary
- Perfect formal verification
- Documenting every AWS/IAM detail in this repo (capture what matters)

---

## Security Principles

- **Least privilege:** services get the minimum permissions required
- **Defense in depth:** multiple layers of controls (network + IAM + scanning + validation)
- **Treat uploads as hostile:** untrusted until scanned and explicitly marked clean
- **No secret material in git:** secrets come from environment or a secret manager
- **Auditability:** key actions have traceable logs/metadata (without storing secrets)

---

## Ingress & Exposure

### Development (ngrok)
ngrok can expose the backend API for webhook or integration testing. This is convenient—and dangerous if careless.

Controls:
- Prefer short-lived ngrok tunnels
- Restrict which endpoints must be reachable externally
- Require auth even in development when possible
- Avoid exposing admin/debug routes

Rules:
- Never log credentials or tokens
- Never commit ngrok URLs, tokens, or configs to git
- Treat dev exposure as temporary, not a deployment model

### Production (AWS)
Production ingress should be stable and protected by AWS networking and security controls.

Controls (typical):
- HTTPS termination at a managed ingress (ALB/API Gateway)
- WAF/rate limiting where appropriate
- Security groups / VPC boundaries
- Strict IAM permissions for access to storage/queues/datastores

---

## Secrets Management

Requirements:
- `.env` files are local-only and must never be committed
- All secrets are provided via environment variables or a secrets manager
- Do not print secrets in logs, exceptions, or debug output

Good patterns:
- `docs/` describes what variables exist (names), not their values
- Local development uses `.env` + `.env.example` (example has no secrets)
- Production uses AWS-managed secret storage

---

## File Upload Handling & GuardDuty Malware Protection

Uploaded files are untrusted input and must be isolated and scanned.

### High-level policy
A file is not considered "accepted" until:
1) it is stored in S3, and
2) AWS GuardDuty Malware Protection for S3 scan completes successfully, and
3) metadata is updated to mark the file CLEAN (`scan_status=CLEAN`)

### Implemented architecture (S3 → GuardDuty → EventBridge → Lambda)

    [FE] presign + upload (<=5MB)
      |
      v
    [S3] untrusted object (key includes document_id)
      |
      v
    [GuardDuty Malware Protection for S3] (AWS-managed scan; no file download required)
      |
      v
    [EventBridge] receives GuardDuty finding
      |
      v
    [Lambda: guardduty_scan_forwarder]
      |
      | extracts document_id from S3 key
      | verdict source of truth: S3 object tag GuardDutyMalwareScanStatus
      | (if verdict not in event, Lambda calls S3 GetObjectTagging)
      | maps verdict -> CLEAN/INFECTED/ERROR
      |
      +--> NO_THREATS_FOUND -> backend callback -> DB scan_status=CLEAN (download allowed)
      +--> THREATS_FOUND    -> backend callback -> DB scan_status=INFECTED (download blocked)
      +--> ERROR/UNKNOWN    -> backend callback -> DB scan_status=ERROR (download blocked)

### Security properties

- **AWS-managed scanning:** GuardDuty performs malware scanning without us downloading or processing untrusted files.
- **No file handling:** The forwarder Lambda never downloads file contents. If the verdict is missing from the event, it only reads **object tags** via `GetObjectTagging`.
- **Least privilege:** Lambda needs only EventBridge trigger permissions and network access to call the backend callback.
- **Backend enforcement:** Download endpoints are blocked unless `scan_status == CLEAN`.
- **Audit trail:** Infected documents remain in the DB with `scan_status=INFECTED`; S3 object remains in place but download is blocked.

### Required IAM (Lambda)

The Lambda forwarder must be able to read object tags when EventBridge does not include them:

- Action: `s3:GetObjectTagging`
- Resource (scoped to the upload prefix):
  - `arn:aws:s3:::job-tracker-documents-0407/job-tracker/*`

### Storage model
- **Single S3 bucket:** all uploaded files go to the same bucket with a key structure that embeds `document_id`.
- **No quarantine prefix:** GuardDuty marks infected objects but does not move them. Backend blocks downloads based on `scan_status`.
- **Clean state:** represented by `scan_status=CLEAN` in DB; GuardDuty finding is `NO_THREATS_FOUND`.

### Scan outcomes
- CLEAN: `scan_status=CLEAN`; downstream processing allowed (download enabled)
- INFECTED: `scan_status=INFECTED`; downstream processing forbidden (download blocked; file remains in S3 for audit)
- ERROR: `scan_status=ERROR`; scan failed or status unknown; file remains untrusted (download blocked)

### Operational notes
- GuardDuty Malware Protection for S3 must be enabled in the AWS account/region.
- EventBridge rule must be configured to forward GuardDuty findings to the Lambda.
- No file downloads or ClamAV definitions management required.
- Lambda is stateless and idempotent (safe for EventBridge retries).

### Secrets: Lambda → backend callback

The callback endpoint is protected by a shared secret header:
- Header: `x-doc-scan-secret` (preferred) or `x-internal-token` (legacy)
- Value: `DOC_SCAN_SHARED_SECRET` (backend + Lambda env var)

No secrets are committed to git; they are configured via environment variables.

---

## Authorization & Access Control

Design goals:
- UI and API enforce access controls consistently
- Protect any endpoints that mutate state
- Avoid “dev-only backdoors” that can drift into production

If authentication exists:
- Prefer short-lived access tokens
- Store tokens securely (avoid leaking to logs)
- Apply consistent permission checks in backend service layer

---

## Data Protection

- Minimize stored PII (only store what is necessary)
- Encrypt data at rest (managed by AWS service defaults when available)
- Encrypt data in transit (HTTPS everywhere)
- Avoid storing raw uploaded documents in plaintext outside controlled storage zones

---

## Logging & Audit

Logging goals:
- Provide enough signal to debug issues
- Avoid storing secrets or sensitive content

Rules:
- Do not log request bodies containing credentials
- Do not log file contents
- Prefer logging:
  - request IDs
  - user IDs (if applicable)
  - high-level action and result
  - scan state transitions (PENDING → CLEAN/REJECTED)
- Store run outputs under `logs/` (ignored by default in git)

---

## Dev Hygiene Checklist

- `.env` not committed
- ngrok used only when needed and rotated regularly
- no sensitive artifacts in `logs/` that could be accidentally committed
- temporary scripts stay in `temp_scripts/`
- `docs/ai/DECISIONS.md` updated when a security-relevant decision is made

---

## Open Items (fill in as you implement)
- Which AWS services are used for storage, queues, and persistence
- Exact upload flow (direct to backend vs pre-signed upload)
- Rate limiting strategy
- Token/session mechanism
- WAF configuration (if applicable)