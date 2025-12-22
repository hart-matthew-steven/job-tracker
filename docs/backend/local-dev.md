# Backend Local Development

This document describes how to run and work on the backend API locally.

---

## Requirements

- Python (version TBD)
- Virtual environment tool (venv, virtualenv, etc.)

---

## Running the Backend

From the repo root:

    cd backend
    # create and activate virtual environment
    # install dependencies
    # start the API server

Exact commands may vary and should be documented once finalized.

---

## Environment Configuration

- Configuration is provided via environment variables.
- `.env` files are local-only and must never be committed.
- A generated `backend/.env.example` file is used to document backend variable names (no values).

Do not document secret values.

### Email configuration (backend)

`EMAIL_PROVIDER` defaults to **`resend`** when unset.

Supported providers:
- `resend` (default): requires `FROM_EMAIL` + `RESEND_API_KEY`
- `ses`: requires `AWS_REGION` + `FROM_EMAIL`
- `gmail`: uses SMTP and preserves `SMTP_FROM_EMAIL` as the From address

Legacy alias:
- `smtp` is treated as `gmail`

---

## Local Integrations

Development may include:
- local persistence (or dev database)
- AWS dev resources
- ngrok for external access (temporary)

Security rules still apply:
- do not bypass file scanning
- do not log secrets
- do not expose unnecessary endpoints

---

## Debugging Tips

- Enable structured logging (without secrets)
- Use request IDs for tracing
- Validate upload/scan flows end-to-end

---

## Updating this Document

Update this file when:
- backend startup process changes
- env/config expectations change
- local integration patterns change