# Frontend Local Development

This document describes how to run and work on the frontend locally.

---

## Requirements

- Node.js (version TBD)
- npm (or compatible package manager)

---

## Running the Frontend

From the repo root:

```bash
cd frontend-web
npm install
VITE_API_BASE_URL=http://localhost:8000 \
VITE_TURNSTILE_SITE_KEY=1x00000000000000000000AA \
npm run dev
```

`VITE_API_BASE_URL` tells the SPA which backend to call. When pointing at ngrok or a staging URL, export that value before running `npm run dev`. Production builds get the value injected at build time via GitHub Actions—there is no `.env.production` checked into the repo.

`VITE_TURNSTILE_SITE_KEY` configures the Cloudflare Turnstile widget rendered on `/register`. Use Cloudflare’s public test site key (`1x00000000000000000000AA`) for local dev unless you have provisioned a dedicated Turnstile site.

Optional: set `VITE_IDLE_TIMEOUT_MINUTES` to override the default 30-minute idle logout timer during local testing.

Note: `/demo/board` is a static preview that renders seeded data without calling the backend, so it works even if the API is offline. Use it when building marketing tweaks or debugging the landing CTA flow.

---

## Backend Connectivity

- All API calls go through `src/api.ts` (general backend routes) or `src/api/authCognito.ts` (Cognito Option-B flows).
- In development the backend typically runs at `http://localhost:8000`. When using ngrok, set `VITE_API_BASE_URL` to the tunnel URL so cookies and redirects stay consistent.
- The frontend never calls Cognito directly—the SPA talks only to `/auth/cognito/*` and receives Cognito tokens from our backend responses (the SPA stores them in memory + sessionStorage).

### Auth & MFA flow (Chunk 7)

1. `/register` → `POST /auth/cognito/signup` (payload includes `turnstile_token`)
2. `/verify` → screen that calls `/auth/cognito/verification/send` (resend button) and `/auth/cognito/verification/confirm`. Both endpoints are public so users can finish verification before logging in. Legacy `/auth/cognito/confirm` exists only for fallback migrations.
3. `/login` → `POST /auth/cognito/login`
   - `status=OK` → store the Job Tracker access token in sessionStorage and proceed
   - `status=CHALLENGE` + `MFA_SETUP` → `/mfa/setup` → `/auth/cognito/mfa/setup` + `/auth/cognito/mfa/verify`
   - `status=CHALLENGE` + `SOFTWARE_TOKEN_MFA` → `/mfa/code` → `/auth/cognito/challenge`
4. `/auth/cognito/logout` is a best-effort endpoint; the SPA clears its stored Cognito tokens (memory + sessionStorage) through `AuthProvider.logout()`.

---

## Development Guidelines

- Prefer fast feedback over premature optimization
- Keep API calls centralized
- Handle loading and error states consistently
- Preserve UI behavior during refactors unless explicitly changing UX

---

## Debugging Tips

- Use browser dev tools to confirm requests hit `/auth/cognito/*` and that responses include `status`/`next_step`.
- If MFA screens loop, confirm the backend has valid `COGNITO_*` env vars and that the SPA is pointing at the same origin specified in `CORS_ORIGINS`.
- When using ngrok, update both `VITE_API_BASE_URL` **and** backend CORS origins to include the ngrok HTTPS URL—otherwise refresh or challenge calls will fail silently.

---

## Updating this Document

Update this file when:
- frontend dev workflow changes
- API base URL configuration changes
- new dev-only tools or steps are added