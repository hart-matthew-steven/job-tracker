from __future__ import annotations

from fastapi import Header

from app.services.limits import generate_correlation_id


def get_correlation_id(x_request_id: str | None = Header(None)) -> str:
    return generate_correlation_id(x_request_id)


