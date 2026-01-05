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

---

## Deployment Workflows (production)

Two additional workflows run on pushes to `main` to deploy the latest code:

- **Backend deploy** — `.github/workflows/backend-deploy.yml`
  - Builds the backend image with `docker buildx --platform linux/amd64`
  - Pushes to ECR
  - Assumes the App Runner deploy role via GitHub OIDC (`AWS_ROLE_ARN_BACKEND_DEPLOY`)
  - Runs `scripts/deploy_apprunner.py` to update the App Runner service, wait for health checks, and roll back automatically on failure

- **Frontend deploy** — `.github/workflows/frontend-deploy.yml`
  - Runs `npm ci && npm run build`
  - Uploads the build to S3 as a versioned release
  - Promotes the new release via `scripts/deploy_frontend.py` (updates `_releases/current.json`, invalidates CloudFront, and rolls back if the health check fails)
  - Requires the CloudFront/S3 deploy role via OIDC (`AWS_ROLE_ARN_FRONTEND_DEPLOY`)

### Required Secrets / Variables

Configure these in the GitHub repo settings:

- `AWS_REGION`
- `AWS_ROLE_ARN_BACKEND` / `AWS_ROLE_ARN_FRONTEND` (CI)
- `AWS_ROLE_ARN_BACKEND_DEPLOY` / `AWS_ROLE_ARN_FRONTEND_DEPLOY`
- `BACKEND_ECR_REPO`, `FRONTEND_S3_BUCKET`, `CLOUDFRONT_DISTRIBUTION_ID`, `FRONTEND_URL`
- `VITE_API_BASE_URL`, `VITE_TURNSTILE_SITE_KEY` (used at build time)

### Branch Protection

Once the deploy workflows are healthy, keep the branch protection rule from above so merges to `main` only happen when:

- CI checks (`CI - Backend`, `CI - Frontend`) pass
- Optionally, require the deploy workflows to succeed before GitHub shows “deployments” as successful

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



