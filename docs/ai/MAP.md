# docs/ai/MAP.md
# Repo Map (High-level)

This file is a quick index of "where things live" to reduce repeated re-explaining.
Update it whenever key entry points or folder structure changes.

## Frontend (`frontend-web/`)
- Entry: `frontend-web/src/main.tsx`
- App routes: `frontend-web/src/App.tsx`
- API client: `frontend-web/src/api.ts`
- Cognito auth client + flow: `frontend-web/src/api/authCognito.ts`, `frontend-web/src/pages/auth/{RegisterPage,VerifyEmailPage,LoginPage,MfaSetupPage,MfaChallengePage}.tsx`
- Routes constants: `frontend-web/src/routes/paths.ts`
- Pages:
  - Auth: `frontend-web/src/pages/auth/*`
  - Core: `frontend-web/src/pages/DashboardPage.tsx`, `frontend-web/src/pages/JobsPage.tsx`
  - Account: `frontend-web/src/pages/account/index.tsx`
  - Marketing/demo: `frontend-web/src/pages/landing/LandingPage.tsx` (hero + CTA) and `frontend-web/src/pages/landing/DemoBoardPage.tsx` (read-only board preview for unauthenticated visitors)
- Auth/session plumbing (tokens + idle timeout): `frontend-web/src/auth/AuthProvider.tsx`
- UI building blocks:
  - Layout shell: `frontend-web/src/components/layout/AppShell.tsx`
    - Handles both desktop nav rail and mobile drawer; header always exposes search + “Create job” so primary actions never hide behind the drawer.
  - Current user context provider (`src/context/CurrentUserContext.tsx`) shares `useCurrentUser()` state (including `ui_preferences`) across the tree
  - Toasts: `frontend-web/src/components/ui/ToastProvider.tsx`
  - Modal: `frontend-web/src/components/ui/Modal.tsx`
  - Password helpers: `frontend-web/src/lib/passwordPolicy.ts`, `frontend-web/src/components/forms/PasswordRequirements.tsx`
- Jobs page submodules: `frontend-web/src/pages/jobs/*`
- Frontend tests: `frontend-web/src/**/*.test.tsx` (Vitest)

## Backend (`backend/`)
- Entry: `backend/app/main.py` (expected)
- Routes: `backend/app/routes/` (expected)
  - Job detail bundle lives in `backend/app/routes/job_applications.py` (`GET /jobs/{job_id}/details`)
- Services: `backend/app/services/` (expected)
- Core (auth/config/db): `backend/app/core/` (expected)
  - Password policy enforcement helpers: `backend/app/core/password_policy.py`
  - DB config exposes separate runtime vs migrator credentials (`DB_APP_*`, `DB_MIGRATOR_*`) via `settings.database_url` / `settings.migrations_database_url`
- Auth (Cognito migration): `backend/app/auth/`
  - Identity model: `backend/app/auth/identity.py` (canonical `Identity` dataclass)
  - Cognito JWT verifier: `backend/app/auth/cognito.py`
  - User model: `backend/app/models/user.py` (includes `cognito_sub`, `auth_provider`, `name` NOT NULL)
  - User service (JIT provisioning + name normalization): `backend/app/services/users.py`
  - BFF router: `backend/app/routes/auth_cognito.py` (signup/confirm/login/challenge/MFA/logout)
  - Cognito API helper: `backend/app/services/cognito_client.py`
  - Debug endpoints: `/auth/debug/token-info`, `/auth/debug/identity` (disabled by default)
  - Auth dependencies: `backend/app/dependencies/auth.py` (enforces Cognito-authenticated users)
- Models: `backend/app/models/` (expected)
- Schemas: `backend/app/schemas/` (expected)
- Backend tests: `backend/tests/` (pytest)
- Backend env var reference: `backend/.env.example` (generated, names only)
- User preferences API: `backend/app/routes/users.py` (`/users/me`, `/users/me/settings`, `/users/me/ui-preferences`)
- Billing:
  - Config: `STRIPE_PRICE_MAP` parsing + helpers live in `backend/app/core/config.py` (`StripeCreditPack`, `settings.get_stripe_pack()`).
  - Routes: `/billing/*` in `backend/app/routes/billing.py` (balances/ledger/me/packs) and `/billing/stripe/*` in `backend/app/routes/stripe_billing.py` (checkout + webhook).
  - Service: `backend/app/services/stripe.py` (customer linking, pack/key checkout sessions, transactional webhook processing writing to `stripe_events` + `credit_ledger`).
  - Models: `backend/app/models/credit.py` (`credit_ledger`, `ai_usage`) and `backend/app/models/stripe_event.py` (`status`, `error_message`, `processed_at`).
- Deployment: README "Production deployment (AWS App Runner)" section documents the ECR/App Runner flow (buildx `linux/amd64`, Secrets Manager env injection, `api.jobapptracker.dev` endpoint).

## Architecture Docs
- Overview: `docs/architecture/overview.md`
- Data flow: `docs/architecture/data-flow.md`
- Security: `docs/architecture/security.md`
- Cognito Option B (BFF) + Pre Sign-up + Email verification: `docs/architecture/cognito-option-b.md`

## Lambdas
- GuardDuty forwarding Lambda: `lambda/guardduty_scan_forwarder/`
- Cognito Pre Sign-up Lambda: `lambda/cognito_pre_signup/`

## AI Docs
- Memory: `docs/ai/MEMORY.md`
- Decisions: `docs/ai/DECISIONS.md`
- Repo map: `docs/ai/MAP.md`

## CI/CD + Scripts
- GitHub Actions workflows:
  - Backend deploy: `.github/workflows/backend-deploy.yml`
  - Frontend deploy: `.github/workflows/frontend-deploy.yml`
  - CI quality gates: `.github/workflows/ci-backend.yml`, `.github/workflows/ci-frontend.yml`
- Deployment scripts:
  - Backend/App Runner: `scripts/deploy_apprunner.py`
  - Frontend/S3+CloudFront: `scripts/deploy_frontend.py`

## Logs (ignored by default in Git)
- `tools/` (repo utilities)
  - Generate backend env var example: `tools/generate_env_example.py`
- AI outputs: `logs/ai/`
- Script outputs: `logs/scripts/`