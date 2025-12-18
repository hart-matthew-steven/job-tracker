# Frontend Rules (Web – React + Vite)

## Scope
These rules apply **only** to the web frontend located at:

    frontend-web/

They do **not** apply to any future mobile or native clients.

When an iOS frontend is introduced (e.g. `frontend-ios/`), it will have
its own dedicated rule file (e.g. `15-ios.md`) with platform-specific guidance.

---

## Stack Assumptions
- React + Vite
- JavaScript (not TypeScript) unless explicitly requested

---

## Code Style
- Prefer simple, readable components.
- Keep components small and focused.
- Split files when they become difficult to scan quickly.
- Favor clarity over abstraction.

---

## Data & API Calls
- Centralize API calls in a small, shared client module.
- Avoid scattering `fetch` / HTTP calls across unrelated components.
- Standardize loading, error, and empty states.
- Handle API errors consistently and predictably.

---

## Refactor Preferences
- Reduce duplication.
- Improve naming and component boundaries.
- Keep refactors mechanical and reviewable.
- Preserve existing UI/UX behavior by default.

---

## UI Behavior
- Do not change user-facing behavior unless explicitly requested.
- If a refactor affects rendering, navigation, forms, or state flow,
  call it out **before** implementing.

---

## Documentation
- Comment only non-obvious logic.
- Prefer short “why” comments over narrating what the code already says.
- Frontend conventions and structure should be documented under:
  - `docs/frontend/`