# docs/ai/DECISIONS.md
# Decisions (ADR-lite)

Record decisions that affect structure or long-term direction.

## Format
- Date:
- Decision:
- Rationale:
- Consequences:

---

## 2025-12-18 — Repo hygiene boundaries (docs/logs/temp scripts)
- Decision: Separate documentation, outputs/logs, and one-off scripts into top-level folders:
  - `docs/` for documentation
  - `logs/` for run output and artifacts
  - `temp_scripts/` for disposable scripts
- Rationale: Keep source code clean, reduce noise in commits, and make troubleshooting artifacts easy to locate.
- Consequences:
  - `logs/` and most of `temp_scripts/` are ignored by default in Git.
  - Useful artifacts must be committed intentionally.

---

## 2025-12-18 — Durable AI memory is repo-managed
- Decision: Durable “memory” is written to version-controlled docs instead of relying on hidden chat history.
- Rationale: Predictable context, lower costs, auditable work, easier onboarding for future readers.
- Consequences:
  - After meaningful changes, update `docs/ai/MEMORY.md`.
  - Record tradeoffs in this file.

---

## 2025-12-18 — Cursor context control
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
  - **Superseded:** Removed in Chunk 7 when Cognito tokens became the only credential type and refresh cookies/DB tables were deleted.

---

## 2025-12-18 — Email verification delivery via SES (boto3)
- Decision: (Superseded) Initially send verification emails via AWS SES using `boto3` (SMTP remains optional fallback).
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

---

## 2025-12-19 — Tailwind v4 dark mode uses class-based variant
- Decision: Configure Tailwind v4 `dark:` to follow the `.dark` class (not `prefers-color-scheme`) using `@custom-variant` in `frontend-web/src/index.css`.
- Rationale: Enables app-controlled theme switching (dark/light/system) without relying on OS theme.
- Consequences:
  - Theme changes apply immediately when toggling `.dark` on `<html>`.

---

## 2025-12-19 — Phase 4 refactor approach: extract modules + shared UI class helpers
- Decision: Refactor large frontend pages by extracting pure helpers and presentational components into colocated modules (e.g. `frontend-web/src/pages/jobs/*`). Introduce a tiny shared `frontend-web/src/styles/ui.ts` for repeated Tailwind class strings.
- Rationale: Shrinks large files, reduces duplication, and keeps behavior stable by leaving orchestration/state in the original page while moving UI chunks out.
- Consequences:
  - New modules are intentionally “dumb”/presentational; page owns state.
  - Styling changes are consolidated via shared class constants (still Tailwind; no new deps).

---

## 2025-12-19 — Backend job ownership helpers centralized
- Decision: Centralize repeated job ownership lookup and tag normalization/tag replacement helpers in `backend/app/services/jobs.py` and import them in jobs-related routers.
- Rationale: Removes duplication across routers and keeps route modules thinner and more consistent.
- Consequences:
  - Routers share a single `get_job_for_user(...)` behavior (404 message/shape remains consistent).

---

## 2025-12-19 — Backend auth + documents route helpers extracted into services
- Decision: Extract refresh token/cookie helpers into `backend/app/services/refresh_tokens.py` and document presign validation/replacement helpers into `backend/app/services/documents.py`.
- Rationale: Keep route modules focused on HTTP orchestration and reuse shared policy/validation logic.
- Consequences:
  - Auth routes call shared functions for refresh rotation and cookie handling (behavior unchanged).
  - Document presign endpoint uses shared validation/limits and single-doc replacement logic (behavior unchanged).

---

## 2025-12-19 — Backend standard error response envelope
- Decision: Add global exception handlers in `backend/app/main.py` so API errors follow the standard `{error, message, details?}` contract documented in `docs/api/error-format.md`.
- Rationale: Makes frontend error handling consistent and enables stable tests against API error responses.
- Consequences:
  - `HTTPException` and request validation errors are consistently shaped.
  - Tests can assert stable error codes (e.g., `NOT_FOUND`, `UNAUTHORIZED`, `VALIDATION_ERROR`).

---

## 2025-12-19 — Testing strategy: mock API boundaries, avoid UI snapshots
- Decision: Frontend tests use Vitest + React Testing Library and mock `frontend-web/src/api.ts` rather than snapshot testing or deep component implementation assertions.
- Rationale: Keeps tests resilient while still validating critical user flows and error handling.
- Consequences:
  - Most frontend tests assert on visible text, routing, and API call arguments.
  - Backend tests use pytest with an in-memory SQLite harness for fast, isolated runs.

---

## 2025-12-21 — Malware scanning: Migrated from ClamAV to AWS GuardDuty Malware Protection for S3
- Decision: Migrate from custom ClamAV-based scanning to **AWS GuardDuty Malware Protection for S3** for production reliability.
- Rationale: The ClamAV prototype encountered CDN definition update failures (403 cooldowns) from AWS egress IPs, requiring complex EFS + scheduled updater Lambda workarounds. GuardDuty is AWS-managed, eliminates CDN dependency, and requires no file downloads or custom scanning infrastructure.
- Consequences:
  - **Removed**: All ClamAV Lambda code (`lambda/clamav_scanner/`), SQS-based scan triggers, EFS-based definitions, quarantine copy/delete logic.
  - **Added**: Lightweight Lambda forwarder (`lambda/guardduty_scan_forwarder/`) that parses EventBridge events from GuardDuty and calls the existing backend internal callback.
  - **Backend unchanged**: DB scan fields (`scan_status`, `scan_checked_at`, `scan_message`) and internal callback API (`POST /internal/documents/{document_id}/scan-result`) remain the same integration point.
  - **Frontend unchanged**: Download gating and status display based on `scan_status` remain unchanged.
  - **AWS setup**: GuardDuty Malware Protection for S3 must be enabled; EventBridge rule forwards findings to the Lambda forwarder.
  - **Verdict source of truth**: GuardDuty marks S3 objects with the tag `GuardDutyMalwareScanStatus`. EventBridge events may not include tags, so the Lambda forwarder reads the verdict via S3 `GetObjectTagging` when needed (requires `s3:GetObjectTagging` scoped to the upload prefix).
  - **Infected files**: Remain in S3 but download is blocked by backend; no quarantine/copy needed (GuardDuty marks them).

## 2025-12-23 — Password policy enforcement
- Decision: Introduce configurable password strength rules (`PASSWORD_MIN_LENGTH` default 14) enforced whenever passwords are set/changed. (Initial design also tracked expiration via `PASSWORD_MAX_AGE_DAYS`, which was removed once Cognito became the sole auth provider.)
- Rationale: Aligns with least-privilege goals and security review feedback; prevents weak credentials at creation time while allowing existing accounts to continue signing in.
- Consequences:
  - Backend helper (`app/core/password_policy.py`) validates requirements and rejects weak passwords with structured `WEAK_PASSWORD` errors.
  - Frontend uses shared helper (`src/lib/passwordPolicy.ts`) + `PasswordRequirements` component to block weak passwords client-side and display violations.
  - Docs + `.env.example` document the new env vars.

## 2025-12-23 — Split database credentials (runtime vs migrations)
- Decision: Replace the single `DB_USER`/`DB_PASSWORD` env vars with explicit runtime (`DB_APP_USER`/`DB_APP_PASSWORD`) and migrator (`DB_MIGRATOR_USER`/`DB_MIGRATOR_PASSWORD`) credentials. Runtime services connect via `settings.database_url`, while Alembic uses `settings.migrations_database_url`.
- Rationale: Enforces least privilege so the application pool cannot perform DDL or escalate schema, while migrations retain the permissions they need.
- Consequences:
  - Config defaults fall back so existing setups keep working, but `.env.example`/docs now list both credential sets.
  - Alembic `env.py` chooses the migrator URL (with app-user fallback for local prototyping).
  - Frontend/backends unaffected except for configuration; docs and tooling (e.g., `tools/generate_env_example.py`) reflect the split.

---

## 2025-12-24 — Production hosting via AWS App Runner + Secrets Manager
- Decision: Host the backend on AWS App Runner behind `api.jobapptracker.dev`, pull container images from ECR, and source sensitive configuration from AWS Secrets Manager (env injection) instead of local `.env` files.
- Rationale: App Runner provides managed HTTPS, health checks, autoscaling, and blue/green deploys without maintaining ECS clusters. Secrets Manager keeps JWT secrets, DB credentials, and provider keys centralized and auditable.
- Consequences:
  - Docker builds intended for production must use `docker buildx build --platform linux/amd64` before pushing to ECR; ARM-native images that work on Apple Silicon fail in App Runner otherwise.
  - Deployment workflow: `docker login` to ECR, build & push image, update App Runner service to the new tag (future CI/CD will automate this).
  - Runtime environment variables are no longer read from repo-local `.env` in production; they must be added/updated in Secrets Manager.

## 2025-12-25 — Email verification tokens are single-use + token-versioned sessions
- Decision: Persist hashed verification token IDs (`email_verification_tokens`) so email links are single-use, and embed a `token_version` claim into access tokens so user sessions can be revoked by bumping the column (e.g., on password change or admin deletion).
- Rationale: Prevents recycled verification links from working after resends or account recreation, and ensures users are logged out promptly when credentials change.
- Consequences:
  - `/auth/verify` now errors after a link is used once; resending a verification email invalidates any prior link.
  - Access tokens created before a `token_version` bump are rejected (`401`), forcing re-auth even if a refresh token remains.
  - Change-password flow increments `token_version` in addition to revoking refresh tokens.

---

## 2025-12-29 — Legacy email service removed
- Decision: Remove the backend email service and associated env vars. Email verification/reset flows are owned by Cognito (and future Cognito-triggered Lambdas) instead of the FastAPI app.
- Rationale: After the Cognito cutover, the backend no longer sends emails directly; keeping dormant SMTP/SES/Resend code added maintenance and dependency surface without delivering value.
- Consequences:
  - Deleted `app/services/email.py`, its tests, and `resend` dependency.
  - Removed `EMAIL_*`, `RESEND_API_KEY`, and `SMTP_*` env vars/docs.
  - Future notification/verification work will live alongside Cognito (e.g., Lambda trigger -> Resend) rather than the FastAPI server.

---

## 2025-12-30 — GitHub Actions CI/CD for production deploys
- Decision: Automate production deploys via GitHub Actions workflows:
  - `backend-deploy.yml` builds/pushes backend images to ECR and updates App Runner using `scripts/deploy_apprunner.py`.
  - `frontend-deploy.yml` builds the Vite SPA, versions releases in S3, promotes them, invalidates CloudFront, and exposes rollback metadata via `scripts/deploy_frontend.py`.
- Rationale: Remove manual deploy toil, ensure every merge to `main` publishes consistent artifacts, and capture rollback/health logic in scripts that can be audited.
- Consequences:
  - Workflows assume AWS roles via OIDC; repo secrets now point to role ARNs + target resources.
  - Deploy scripts encapsulate waiting/rollback logic; failures trigger automatic rollback to the last good build.
  - Future work focuses on branch protection, observability, and staged environments rather than hand-deploy steps.

---

## 2025-12-31 — Cognito auth migration: read-only verifier first (Chunk 1)
- Decision: Introduce Cognito JWT verification as a read-only capability before switching auth enforcement.
- Rationale:
  - Incremental migration reduced risk.
  - Verified JWKS/issuer/audience logic before any enforcement.
  - Debug endpoint enabled local token inspection without touching prod.
- Consequences:
  - Added `app/auth/cognito.py` for JWKS fetching/caching and JWT validation.
  - `/auth/debug/token-info` endpoint (dev-only, feature flagged).

---

## 2025-12-31 — Cognito auth migration: unified identity model (Chunk 2)
- Decision: Introduce a canonical `Identity` dataclass (`app/auth/identity.py`). Set `request.state.identity` on every request.
- Rationale:
  - Downstream code should remain provider-agnostic and never inspect raw tokens.
  - Provides a stable reference for AI usage tracking/billing.
- Consequences:
  - `Identity` captures `user_id`, `auth_provider`, `external_subject`, `email`, `is_authenticated`.
  - `/auth/debug/identity` endpoint for dev-only inspection.

---

## 2025-12-31 — Cognito auth migration: profile completion enforcement (Chunk 3) *(retired)*
- Decision (superseded by Chunk 5): Introduce `UserProfile` model and middleware to gate Cognito users until they complete their profile. Custom auth users bypass this gate entirely.
- Rationale:
  - AI features and billing require a consistent user record before resource consumption.
  - iOS onboarding needs a clear profile completion step.
  - Gating ensures data integrity — users can't create jobs/notes until their profile exists.
  - Keeping custom auth users ungated provided backward compatibility during migration.
- Consequences:
  - New `user_profiles` table tracks: `user_id`, `auth_provider`, `external_subject`, `email`, `profile_completed`.
  - Profile gating middleware returns `403 PROFILE_INCOMPLETE` for protected routes when profile is incomplete.
  - Allowed routes for incomplete profiles: `/health`, `/me/profile`, `/me/profile/complete`, `/auth/*`.
  - Profiles auto-created on first Cognito request (idempotent).
  - `/me/profile` and `/me/profile/complete` endpoints added.
  - Historical rollback (pre-cutover) involved disabling the middleware.

---

## 2025-12-31 — Cognito auth migration: backend authorization + JIT users (Chunk 4)
- Decision: Make Cognito the primary authentication source with user auto-provisioning. Add `cognito_sub`/`auth_provider` metadata to the User model.
- Rationale:
  - Consistent user identity across clients (web, iOS) requires a single source of truth.
  - JIT provisioning eliminates separate signup flows — Cognito owns user registration.
  - Profile completion gating ensures users exist in DB before consuming resources.
  - Using the User model (not separate UserProfile) simplifies authorization queries.
- Consequences:
  - User model gained `cognito_sub` (unique) and `auth_provider`.
  - `password_hash` became nullable, anticipating eventual removal.
  - Migration `g8b9c0d1e2f3_add_cognito_fields_to_users.py`.
  - Identity middleware now provisions users on first Cognito-authenticated request.
  - AI features can safely key on `cognito_sub`.

---

## 2025-12-31 — Cognito auth migration: Option B BFF endpoints (Chunk 5)
- Decision: Remove the temporary profile gate + `user_profiles` table and introduce backend-driven Cognito flows (`/auth/cognito/*`) so the SPA never talks to Cognito directly.
- Rationale:
  - Cognito already requires name + email; storing a duplicate profile table created churn without delivering value.
  - Backend-for-Frontend keeps session issuance, logging, and MFA UX consistent while still honouring Cognito’s security posture.
  - Handling TOTP challenges server-side simplifies frontend work and future iOS/native clients.
  - Keeping `cognito_sub` on `users` allows AI/billing systems to key on a single identifier, regardless of client.
- Consequences:
  - Migration `h1c2d3e4f5a6_remove_profile_tables.py` dropped `user_profiles`, removed `users.profile_completed_at`, and enforced `users.name` NOT NULL.
  - Added `app/services/cognito_client.py` and `app/routes/auth_cognito.py`.
  - SPA now talks only to backend endpoints; responses expose deterministic `status`/`next_step`.

---

## 2025-12-31 — Cognito auth migration: TOTP enforcement + challenge contract (Chunk 6)
- Decision: Normalize `/auth/cognito/*` responses so the frontend can render a custom UI for required TOTP MFA without Cognito-specific knowledge.
- Rationale:
  - Cognito challenges are verbose/unstable; the SPA needs a stable `next_step`.
  - MFA setup vs. MFA entry require different UX flows but should reuse the same backend session.
  - Returning `session` + `next_step` lets iOS/SPAs drive the flow without re-implementing Cognito SDKs.
- Consequences:
  - `CognitoAuthResponse.status` is now `OK` or `CHALLENGE`, with `next_step` ∈ {`MFA_SETUP`, `SOFTWARE_TOKEN_MFA`, `NEW_PASSWORD_REQUIRED`, `CUSTOM_CHALLENGE`, `UNKNOWN`}.
  - `/auth/cognito/mfa/setup` returns `{secret_code, otpauth_uri, session}`; `/auth/cognito/mfa/verify` responds to the `MFA_SETUP` challenge with `ANSWER=SUCCESS`.
  - `/auth/cognito/challenge` expects explicit `responses` (e.g., `SOFTWARE_TOKEN_MFA_CODE`) and always echoes `session` + `next_step`.
  - Tests (`tests/test_auth_cognito_bff.py`) cover login OK, MFA_SETUP, SOFTWARE_TOKEN_MFA, OTP setup/verify, and refresh-cookie issuance.
  - Documentation (`README.md`, `docs/architecture/cognito-option-b.md`, `docs/architecture/security.md`, `docs/ai/*`) now includes the curl-based reference flow.

---
## 2025-12-31 — Cognito auth migration: production cutover (Chunk 7)
- Decision: Remove legacy custom auth, rely solely on Cognito-issued tokens (access/id/refresh), and expose the refresh flow via `/auth/cognito/refresh`.
- Rationale:
  - Simplifies security posture and removes dual-mode edge cases.
  - Unlocks native/iOS clients (same API contract) and future passkey work.
- Consequences:
  - Migration `cognito_cutover_cleanup` dropped refresh/email-verification tables and password metadata; `cognito_sub` is `NOT NULL`.
  - Backend rejects non-Cognito Bearer tokens.
  - SPA stores tokens in memory/sessionStorage; refresh tokens never touch cookies/localStorage.
  - Rate limiting + structured logging tightened around `/auth/cognito/*`.

---

## 2026-01-01 — Signup bot protection (Chunk 8)
- Decision: Gate `/auth/cognito/signup` behind Cloudflare Turnstile (invisible mode) and verify tokens server-side before calling Cognito.
- Rationale:
  - Automated signups were the last unguarded way to burn Cognito/email/MFA quota and bootstrap abusive accounts for future AI features.
  - Turnstile gives us a privacy-friendly, UX-light CAPTCHA with a simple verification API and no Google account dependency.
- Consequences:
  - Frontend loads the Turnstile widget on `/register`, stores tokens in memory, and resets the widget after each submit.
  - Backend module `app/services/turnstile.py` posts tokens to Cloudflare via `https://challenges.cloudflare.com/turnstile/v0/siteverify` with short timeouts. Missing config fails closed (HTTP 503) so signup never bypasses CAPTCHA accidentally.
  - Signup schema (`CognitoSignupIn`) gained `turnstile_token`. Tests cover happy-path, missing token, verification failure, and network errors.
  - New env vars (`TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `VITE_TURNSTILE_SITE_KEY`) documented in README/docs.

## 2026-01-01 — Cognito emails via Resend (Chunk 9)
- Decision: Introduce a standalone Cognito Custom Message Lambda (container image) that renders branded templates and sends through Resend’s official Python SDK.
- Rationale:
  - Cognito’s default SES emails are unbranded and can confuse users; we want consistent messaging from `jobapptracker.dev`.
  - Using Resend SDK (instead of raw HTTP) keeps the integration small, typed, and easier to upgrade.
  - Secrets live in AWS Secrets Manager with optional env overrides so we don’t bake API keys into images.
- Consequences:
  - New code under `lambda/cognito_custom_message/` with templates, requirements, Dockerfile, and pytest coverage (Resend + Secrets Manager mocked). **(Superseded by 2026-01-05 decision below.)**
  - Lambda fails closed—if Resend errors we raise, so Cognito doesn’t send its fallback email.
  - Documentation: `README.md` (overview + build/push instructions), `docs/auth-cognito-email.md`, and `docs/ai/*` now describe the flow and security posture.

## 2026-01-01 — Retire Cognito email lambda (Chunk 1B cleanup)
- Decision: Remove the Cognito Custom Message Lambda code/docs because the AWS resources were deleted and the architecture reverted to Cognito’s default email sender.
- Rationale:
  - Keeping dead code and deployment steps causes drift and confuses runbooks/CI.
  - Resend-specific env vars/tests/templates were unused elsewhere.
- Consequences:
  - Deleted `lambda/cognito_custom_message/` and `docs/auth-cognito-email.md`.
  - `.env.example`, README, and `docs/ai/*` no longer mention Resend-trigger Lambda work; Cognito default emails are documented as the current state.
  - GuardDuty lambda and other services remain untouched.

## 2026-01-02 — Cognito Pre Sign-up Lambda (Chunk 10)
- Decision: Add a tiny Pre Sign-up Lambda that auto-confirms users and disables Cognito-managed email verification while we own verification out of band.
- Rationale:
  - Cognito’s default confirmation emails conflict with the planned Resend workflows.
  - Auto-confirming keeps signup friction low and avoids support tickets for missing codes.
- Consequences:
  - New lambda under `lambda/cognito_pre_signup/` (container image, handler, README).
  - Documentation updated (`README.md`, `docs/architecture/cognito-option-b.md`, `docs/architecture/security.md`, `docs/ai/*`).
  - Lambda performs no network calls or secret access; it only flips response flags.

## 2026-01-03 — App-enforced email verification (Chunk 11)
- Decision: Store hashed verification codes in our DB, send via Resend, and block API access until users confirm the code.
- Rationale:
  - Cognito email confirmation was disabled by the Pre Sign-up Lambda; we still need a trustworthy verification state for AI billing/iOS parity.
  - Owning the flow lets us throttle resend abuse, support custom templates, and keep DB + Cognito in sync.
- Consequences:
  - New table `email_verification_codes`, `users` regained `is_email_verified`/`email_verified_at`.
  - Endpoints: `/auth/cognito/verification/send` and `/auth/cognito/verification/confirm` are public (rate-limited, salted SHA-256 hashes, TTL/cooldown). Signup links directly to `/verify` so users handle the code before their first login, but if they skip it the API still returns `403 EMAIL_NOT_VERIFIED`.
  - Middleware blocks all other APIs with `403 EMAIL_NOT_VERIFIED` until the DB flag is true; verifying also calls Cognito `AdminUpdateUserAttributes` using `Username=cognito_sub`.
  - Frontend exposes resend/cooldown UI on `/verify` and listens for `EMAIL_NOT_VERIFIED` responses to redirect back if someone logs in before completing the flow.

## 2026-01-03 — Persist UI preferences on users table
- Decision: Store panel collapse/expand state (and similar UI toggles) in `users.ui_preferences` (JSON) and expose them via `GET /users/me` + `PATCH /users/me/ui-preferences`.
- Rationale:
  - Users expect the UI state to follow them across browsers/devices (and the future iOS client).
  - Persisting preferences next to the user record keeps the data model simple and avoids localStorage drift.
- Consequences:
  - New migration `20250107_01_add_ui_preferences.py` adds the JSON column with `{}` default.
  - Backend validates preference keys (`job_details_*_collapsed`) and persists toggles.
  - Frontend hydrates from `user.ui_preferences` and updates via the new endpoint; state survives page refreshes and device changes.

## 2026-01-03 — GuardDuty Lambda pulls scan secret from Secrets Manager
- Decision: Stop storing the document scan shared secret in Lambda env vars and instead store only the secret ARN (`DOC_SCAN_SHARED_SECRET_ARN`). Lambda fetches the value at runtime via AWS Secrets Manager.
- Rationale:
  - Keeps the shared secret out of the function configuration/console.
  - Aligns with App Runner, which already injects the secret from Secrets Manager.
- Consequences:
  - Lambda now requires `secretsmanager:GetSecretValue` permission on the secret ARN.
  - Backend and Lambda secrets stay in sync via Secrets Manager; the callback header (`X-Scan-Secret`) still guards `/jobs/{job_id}/documents/{document_id}/scan-result`.
  - Docs (`docs/architecture/security.md`, `docs/architecture/data-flow.md`, `docs/api/endpoints.md`) reference the new path and secret handling.


---

## 2026-01-05 — Mobile AppShell parity for primary actions
- Decision: keep the “Search” affordance and global “Create job” CTA in the header on every breakpoint rather than hiding Create inside the mobile drawer.
- Rationale:
  - Users on phones/tablets should not have to open the drawer just to create a role or search the board.
  - Aligning mobile and desktop affordances prevents UX drift as we keep iterating on the shell.
- Consequences:
  - The mobile header now renders a search pill plus a compact Create button next to it; the drawer only lists navigation links.
  - Frontend tests (`BoardDrawer.test.tsx`) cover the drawer’s no-reload status changes to guard against regressions uncovered during this tweak.
  - Docs updated (`docs/frontend/overview.md`, `docs/ai/*`, API/architecture/frontend overviews) so future contributors know the intended behavior.

---

## 2026-01-04 — SPA idle timeout handled client-side
- Decision: Add an inactivity timer to the SPA instead of shortening Cognito refresh-token TTLs.
- Rationale:
  - Keeps Cognito configuration stable for active SPA/native clients.
  - Still mitigates risk from abandoned browser tabs on shared machines.
- Consequences:
  - `AuthProvider` listens to keyboard/mouse/touch/scroll/visibility events and clears the session when the timer expires (default 30 minutes, configurable via `VITE_IDLE_TIMEOUT_MINUTES`, minimum 5).
  - Idle logout is purely client-side; backend/stateful components are unchanged.

---

## 2026-01-04 — Bundled job detail endpoint
- Decision: Serve job details, notes, interviews, and recent activity from a single endpoint (`GET /jobs/{job_id}/details`).
- Rationale:
  - JobsPage previously fired four sequential requests whenever the user selected a job; bundling the data materially reduces latency.
  - Keeps the incremental endpoints available for follow-up operations (e.g., deleting a note still refreshes `/jobs/{id}/notes`).
- Consequences:
  - Backend schema gained `JobDetailsBundleOut`; tests assert the bundled response shape.
  - Frontend calls the bundled endpoint first and falls back to `GET /jobs/{id}` only if `job` is missing, keeping existing mutation flows intact.

---

## 2026-01-04 — Activity pagination + infinite scroll
- Decision: Page `/jobs/{id}/activity` with `cursor_id`/`next_cursor` and load additional entries as the user scrolls inside the timeline card.
- Rationale:
  - Returning the entire activity history on every selection bloated the payload and pushed the Documents card far down the screen.
  - Infinite scrolling keeps the UI tight while still letting power users read older activity.
- Consequences:
  - Backend route now returns `{items,next_cursor}` and the details bundle includes the first page of activity plus the cursor.
  - Frontend timeline renders inside a fixed-height container, automatically requests the next page when the user nears the bottom, and shows a spinner/“scroll to load more” hint.

## 2026-01-04 — Public demo board + updated marketing copy
- Decision: Refresh the landing page messaging (remove “private alpha” wording and Jira comparisons) and add a `/demo/board` route that renders a read-only kanban preview without requiring authentication.
- Rationale:
  - Prospects requested a quick way to see the board workflow without creating an account.
  - Referencing competitor brands in the hero copy felt dated, and the “private alpha” badge conflicted with self-serve signup.
- Consequences:
  - Landing page CTAs now point to signup or the demo board; hero text references “enterprise-grade clarity” instead of Jira.
  - Frontend includes `DemoBoardPage.tsx`, which renders seeded cards entirely client-side for unauthenticated visitors.
  - Documentation highlights the demo route so GTM/support can link to it directly.