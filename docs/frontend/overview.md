# Frontend Overview

This document describes the frontend structure and conventions at a high level.

---

## Stack

- React + Vite
- TypeScript
- Vitest + React Testing Library

---

## Responsibilities

- User interface for tracking applications, statuses, notes, and documents
- Calls backend API via a centralized client module
- Presents scan/upload status clearly for user uploads
- Persists user UI preferences (collapsed cards, etc.) by calling `PATCH /users/me/ui-preferences`
- Clears Cognito sessions after a configurable period of inactivity; `AuthProvider` listens to user interaction events and logs out idle tabs (default 30 minutes, override via `VITE_IDLE_TIMEOUT_MINUTES`).
- Hosts the marketing landing page plus `/demo/board`, a read-only board preview rendered entirely client-side so visitors can explore the UI without an account.
- Keeps the AppShell consistent across breakpoints: the header always exposes global search + the “Create job” CTA, while the mobile drawer is reserved for navigation links. This ensures job creation never hides behind a menu on phones/tablets.
- Surfaces prepaid AI credits at all times via the header badge. The badge reads `/billing/credits/balance`, links to `/billing`, and exposes `refresh()` so checkout/AI flows can request a fresh balance after spending or minting credits.

### Board-first workspace (UI revamp snapshot)

- `/board` is the primary route. Query param `jobId` drives the right-side drawer so cards are deep-linkable.
- `AppShell` provides the slim nav rail on desktop, a mobile drawer for navigation only, global Cmd/Ctrl + K search, and the always-present “Create job” button (including on mobile).
- `BoardColumn` lanes are grouped (`Applied`, `Interviewing`, `Offer`, `Closed`) and cap height with infinite scroll (25 cards per load) so 100–300 jobs stay performant.
- `BoardDrawer` loads `GET /jobs/{id}/details` (job + notes + interviews + first page of activity) and drives status changes, momentum buttons, notes, interviews, documents, and timeline pagination without flickering.
- `CommandMenu` hits `/jobs/search` with debounced queries; selecting a card opens the drawer via `?jobId=`.
- Smart suggestions + follow-up pills rely on server-computed `needs_follow_up` and momentum fields (`last_action_at`, `next_action_at`, `next_action_title`).

### Billing and credits

- `/billing` is the billing hub. It shows the latest balance, a reminder that credits gate AI usage, and the three configured Stripe packs. Pack metadata (price, credits, currency) is fetched from `/billing/packs`, while UI labels/badges/descriptions come from `src/config/billing.ts` so we can rename packs without touching the backend.
- `VITE_BILLING_PACK_CONFIG` lets you override those display labels per environment. Example for `frontend-web/.env`:

  ```bash
  VITE_BILLING_PACK_CONFIG='{"starter":{"label":"Starter"},"pro":{"label":"Plus","badge":"Most popular"},"expert":{"label":"Max","badge":"Best value"}}'
  ```

- Each pack calls `POST /billing/stripe/checkout` with its `pack_key` and redirects to the returned Stripe URL.
- `/billing/return` (and the legacy `/billing/stripe/success|cancelled` paths) show a success or cancel state and call `credits.refresh()` so balances stay in sync with the webhook.

---

## Structure

Expected entry points:
- `frontend-web/src/main.tsx`
- `frontend-web/src/App.tsx`
- `frontend-web/src/api/authCognito.ts` (Cognito Option-B client)

Recommended organization:
- `src/pages/` for route-level views
- `src/pages/account/` for account/profile/settings screens
- `src/pages/auth/` for login/register/confirm/MFA (Cognito flow)
- `src/pages/auth/VerifyEmailPage.tsx` handles the Resend code flow; it can be reached with or without a Cognito session immediately after signup.
- `src/routes/` for route path constants
- `src/components/` for reusable UI components
- `src/components/jobs/` for job-related UI (list/detail/notes)
- `src/components/layout/` for shell/layout building blocks (e.g., `AppShell.tsx`)
- `src/api.ts` for backend calls, `src/api/authCognito.ts` for Cognito `/auth/cognito/*`
- `src/hooks/` for shared logic
- `src/types/` for shared domain + API DTO types

Notable hooks:
- `src/hooks/useCurrentUser.ts` — current user fetch state
- `src/hooks/useSettings.ts` — user settings fetch/update state (auto refresh frequency)
- `src/context/CurrentUserContext.tsx` — provides `useCurrentUser()` data to the tree so components can read `ui_preferences`

---

## Conventions

- Keep components small and focused
- Prefer predictable patterns over clever abstraction
- Centralize API calls (either `src/api.ts` or `src/api/authCognito.ts`)
- Cognito access/id/refresh tokens live in memory + `sessionStorage`. When you need to clear auth, call `useAuth().logout()` so the storage tier is wiped and the backend sees the logout best-effort request (`/auth/cognito/logout`).

---

## Tests

Frontend tests live alongside code as `*.test.tsx` and are run via Vitest:

- `cd frontend-web && npm test`

The suite focuses on:
- user flows (auth, jobs, documents, settings)
- API boundary behavior (mocked `src/api.ts`)
- toast/error handling

---

## Updating this document

Update when:
- routing structure changes
- state management approach changes
- API client strategy changes