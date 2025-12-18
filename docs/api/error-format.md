# API Error Format

This document defines the standard error response format for the Job Tracker backend API.

The goal is to ensure errors are:
- consistent
- actionable
- easy for the frontend to handle
- safe (no sensitive data leaked)

---

## Standard Error Shape

All error responses should follow this structure:

    {
      "error": "<STABLE_ERROR_CODE>",
      "message": "<human-readable message>",
      "details": { ... }   // optional
    }

### Fields

- `error`
  - A stable, machine-readable error code
  - Intended for programmatic handling on the frontend
  - Example: `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`

- `message`
  - Human-readable explanation
  - Safe to display to end users
  - Should not expose internal implementation details

- `details` (optional)
  - Structured metadata to aid debugging
  - Should never include secrets or sensitive payloads

---

## Examples

### Validation Error

    {
      "error": "VALIDATION_ERROR",
      "message": "Invalid request payload",
      "details": {
        "field": "status"
      }
    }

### Not Found

    {
      "error": "NOT_FOUND",
      "message": "Application not found"
    }

### Unauthorized

    {
      "error": "UNAUTHORIZED",
      "message": "Authentication required"
    }

---

## HTTP Status Codes

Errors should use appropriate HTTP status codes:

- `400` — validation errors
- `401` — unauthenticated
- `403` — unauthorized
- `404` — resource not found
- `409` — conflict
- `500` — internal server error

The HTTP status code and the `error` field should be consistent.

---

## Logging Rules

- Do not log sensitive request bodies.
- Do not log credentials or tokens.
- Internal stack traces should be logged server-side only.
- The client should never receive stack traces.

---

## Updating this Document

Update this file when:
- error structure changes
- new standard error codes are introduced
- frontend error-handling conventions change