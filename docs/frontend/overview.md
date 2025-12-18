# Frontend Overview

This document describes the frontend structure and conventions at a high level.

---

## Stack

- React + Vite
- TypeScript

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

## Updating this document

Update when:
- routing structure changes
- state management approach changes
- API client strategy changes