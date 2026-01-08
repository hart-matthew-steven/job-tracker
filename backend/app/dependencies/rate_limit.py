from __future__ import annotations

import json
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
        _log_decision(request=request, result=result, route_key=route_key)
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


def _log_decision(*, request: Request, result: RateLimitResult, route_key: str) -> None:
    user = getattr(request.state, "user", None)
    user_id = getattr(user, "id", None)
    payload = {
        "user_id": user_id,
        "route": request.url.path,
        "http_method": request.method,
        "route_key": route_key,
        "limiter_key": result.limiter_key,
        "window_seconds": result.window_seconds,
        "limit": result.limit,
        "current_count": result.count,
        "remaining": result.remaining,
        "reset_epoch": result.window_reset_epoch,
        "decision": "allow" if result.allowed else "block",
    }
    try:
        logger.info(json.dumps(payload, separators=(",", ":")))
    except Exception:  # pragma: no cover - defensive
        logger.exception("Failed to emit rate limit log")

