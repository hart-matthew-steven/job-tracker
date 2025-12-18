# Frontend Overview

This document describes the frontend structure and conventions at a high level.

---

## Stack

- React + Vite
- JavaScript (TypeScript optional in the future)

---

## Responsibilities

- User interface for tracking applications, statuses, notes, and documents
- Calls backend API via a centralized client module
- Presents scan/upload status clearly for user uploads

---

## Structure (fill in once confirmed)

Expected entry points:
- `frontend-web/src/main.jsx`
- `frontend-web/src/App.jsx`

Recommended organization:
- `src/pages/` for route-level views
- `src/components/` for reusable UI components
- `src/components/layout/` for shell/layout building blocks (e.g., `AppShell.jsx`)
- `src/api/` or `src/apiClient.js` for backend calls
- `src/hooks/` for shared logic

Notable hooks (frontend-only for now):
- `src/hooks/useCurrentUser.js` — stubbed current user (API later)
- `src/hooks/useSettings.js` — local settings persisted to `localStorage` (auto refresh frequency)

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