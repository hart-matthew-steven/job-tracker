# Frontend Local Development

This document describes how to run and work on the frontend locally.

---

## Requirements

- Node.js (version TBD)
- npm (or compatible package manager)

---

## Running the Frontend

From the repo root:

    cd frontend
    npm install
    npm run dev

This starts the Vite development server.

---

## Backend Connectivity

- The frontend communicates with the backend via HTTP APIs.
- In development, the backend typically runs locally.
- If the backend is exposed via ngrok, the frontend should point to the ngrok URL.

Configuration options may include:
- environment variables
- a centralized API client configuration file

---

## Development Guidelines

- Prefer fast feedback over premature optimization
- Keep API calls centralized
- Handle loading and error states consistently
- Preserve UI behavior during refactors unless explicitly changing UX

---

## Debugging Tips

- Use browser dev tools for network inspection
- Confirm API base URL is correct
- Watch for CORS issues when using ngrok

---

## Updating this Document

Update this file when:
- frontend dev workflow changes
- API base URL configuration changes
- new dev-only tools or steps are added