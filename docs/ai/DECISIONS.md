# docs/ai/DECISIONS.md
# Decisions (ADR-lite)

Record decisions that affect structure or long-term direction.

## Format
- Date:
- Decision:
- Rationale:
- Consequences:

---

## 2025-01-XX — Repo hygiene boundaries (docs/logs/temp scripts)
- Decision: Separate documentation, outputs/logs, and one-off scripts into top-level folders:
  - `docs/` for documentation
  - `logs/` for run output and artifacts
  - `temp_scripts/` for disposable scripts
- Rationale: Keep source code clean, reduce noise in commits, and make troubleshooting artifacts easy to locate.
- Consequences:
  - `logs/` and most of `temp_scripts/` are ignored by default in Git.
  - Useful artifacts must be committed intentionally.

---

## 2025-01-XX — Durable AI memory is repo-managed
- Decision: Durable “memory” is written to version-controlled docs instead of relying on hidden chat history.
- Rationale: Predictable context, lower costs, auditable work, easier onboarding for future readers.
- Consequences:
  - After meaningful changes, update `docs/ai/MEMORY.md`.
  - Record tradeoffs in this file.

---

## 2025-01-XX — Cursor context control
- Decision: Commit `.cursorignore` and `.cursor/rules/*` to define predictable AI scope and behavior.
- Rationale: Reduce accidental context bloat/cost and keep AI behavior consistent across machines.
- Consequences:
  - Changes to Cursor behavior are reviewable like code.

---

## 2025-12-18 — Auth: access token + refresh cookie
- Decision: Use Bearer JWT access tokens + HttpOnly refresh cookie with DB-stored refresh tokens.
- Rationale: Keeps API auth simple for the SPA while supporting refresh token rotation and revocation.
- Consequences:
  - `/auth/refresh` rotates refresh tokens and returns new access token.
  - `/users/me/change-password` revokes refresh tokens to force re-login.

---

## 2025-12-18 — Email verification delivery via SES (boto3)
- Decision: Send verification emails via AWS SES using `boto3` (SMTP remains optional fallback).
- Rationale: SES is a production-grade path for delivery and aligns with AWS hosting plans.
- Consequences:
  - Requires verified SES identity + appropriate IAM permissions/credentials.
  - Deliverability posture (SPF/DKIM/DMARC) should be addressed for public launch.

---

## 2025-12-18 — User settings persisted on users table
- Decision: Persist user preference `auto_refresh_seconds` on the `users` table and expose via `/users/me/settings`.
- Rationale: Keeps a single-user settings surface area small and avoids separate settings tables prematurely.
- Consequences:
  - Future expansion may warrant a dedicated settings table/schema if preferences grow.