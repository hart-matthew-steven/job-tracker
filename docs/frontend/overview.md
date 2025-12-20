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

---

## Structure

Expected entry points:
- `frontend-web/src/main.tsx`
- `frontend-web/src/App.tsx`

Recommended organization:
- `src/pages/` for route-level views
- `src/pages/account/` for account/profile/settings screens
- `src/routes/` for route path constants
- `src/components/` for reusable UI components
- `src/components/jobs/` for job-related UI (list/detail/notes)
- `src/components/layout/` for shell/layout building blocks (e.g., `AppShell.tsx`)
- `src/api.ts` for backend calls
- `src/hooks/` for shared logic
- `src/types/` for shared domain + API DTO types

Notable hooks:
- `src/hooks/useCurrentUser.ts` — current user fetch state
- `src/hooks/useSettings.ts` — user settings fetch/update state (auto refresh frequency)

---

## Conventions

- Keep components small and focused
- Prefer predictable patterns over clever abstraction
- Do not scatter API calls across unrelated components
- Preserve UI behavior during refactors unless explicitly changing UX

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