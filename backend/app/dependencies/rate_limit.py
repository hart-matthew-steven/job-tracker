from __future__ import annotations

import logging
from typing import Callable

from fastapi import Depends, HTTPException, Request, status

from app.core.config import settings
from app.services.rate_limiter import RateLimitResult, get_rate_limiter

logger = logging.getLogger(__name__)


def require_rate_limit(
    route_key: str,
    *,
    limit: int | None = None,
    window_seconds: int | None = None,
) -> Callable:
    resolved_limit = max(1, limit or settings.RATE_LIMIT_DEFAULT_MAX_REQUESTS)
    resolved_window = max(1, window_seconds or settings.RATE_LIMIT_DEFAULT_WINDOW_SECONDS)

    async def dependency(request: Request) -> None:
        limiter = get_rate_limiter()
        identifier = _resolve_identifier(request)
        result = limiter.check(
            identifier=identifier,
            route_key=route_key,
            limit=resolved_limit,
            window_seconds=resolved_window,
        )
        if not result.allowed:
            retry_after = max(1, result.retry_after_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "RATE_LIMITED",
                    "message": "Too many requests",
                    "details": {
                        "retry_after_seconds": retry_after,
                        "limit": result.limit,
                        "remaining": result.remaining,
                    },
                },
                headers={"Retry-After": str(retry_after)},
            )

    return dependency


def _resolve_identifier(request: Request) -> str:
    user = getattr(request.state, "user", None)
    if user is not None and getattr(user, "id", None):
        return f"user:{user.id}"

    client = request.client
    host = (client.host if client else None) or "unknown"
    return f"ip:{host}"

