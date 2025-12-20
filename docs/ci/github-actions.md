# GitHub Actions CI (lint + tests)

Goal: **run lint + tests on pull requests and block merges to `main` unless checks pass**.

## What’s in this repo

GitHub Actions workflows:
- Backend: `.github/workflows/ci-backend.yml`
  - Ruff (syntax/undefined checks) + pytest
- Frontend: `.github/workflows/ci-frontend.yml`
  - TypeScript typecheck + ESLint + Vitest

They run on:
- Pull requests that touch `backend/**` or `frontend-web/**`
- Pushes to `main`

## Steps you need to do in GitHub (one-time)

### 1) Push these workflow files to GitHub

After you push, go to:
- GitHub repo → **Actions** tab
- Open a recent workflow run to confirm it’s executing.

### 2) Turn on branch protection for `main`

GitHub repo → **Settings** → **Branches** → **Branch protection rules** → **Add rule**

- **Branch name pattern**: `main`
- Enable: **Require a pull request before merging**
- Enable: **Require status checks to pass before merging**
  - Click “Search for status checks…” and select:
    - `CI - Backend / lint-and-test`
    - `CI - Frontend / typecheck-lint-test`
- (Recommended) Enable: **Require branches to be up to date before merging**
- (Recommended) Enable: **Restrict who can push to matching branches** (optional)

Save the rule.

### 3) Verify it blocks merges

Open a PR that changes something under `backend/` or `frontend-web/`.
- You should see the checks run automatically.
- If a check fails, GitHub should prevent merging to `main` until fixed.

## Local commands (same checks as CI)

Frontend:

```bash
cd frontend-web
npm ci
npm run typecheck
npm run lint
npm test
```

Backend:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 -m pytest
```



