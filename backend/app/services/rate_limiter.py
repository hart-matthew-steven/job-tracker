from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Protocol

import boto3

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int
    limit: int
    remaining: int
    count: int
    window_reset_epoch: int
    limiter_key: str
    window_seconds: int


class RateLimiter(Protocol):
    def check(
        self,
        *,
        identifier: str,
        route_key: str,
        limit: int,
        window_seconds: int,
        now: int | None = None,
    ) -> RateLimitResult:
        ...


class NoopRateLimiter:
    """
    Disabled limiter that always allows requests. Used when rate limiting is turned off
    or configuration is incomplete.
    """

    def check(
        self,
        *,
        identifier: str,
        route_key: str,
        limit: int,
        window_seconds: int,
        now: int | None = None,
    ) -> RateLimitResult:
        now_ts = int(now or time.time())
        reset_epoch = now_ts + window_seconds
        limiter_key = f"noop:{route_key}:window:{window_seconds}"
        return RateLimitResult(
            allowed=True,
            retry_after_seconds=0,
            limit=limit,
            remaining=max(0, limit),
            count=0,
            window_reset_epoch=reset_epoch,
            limiter_key=limiter_key,
            window_seconds=window_seconds,
        )


_limiter: RateLimiter | None = None
_lock = threading.Lock()


def get_rate_limiter() -> RateLimiter:
    global _limiter
    if _limiter is not None:
        return _limiter
    with _lock:
        if _limiter is None:
            _limiter = _build_rate_limiter()
    return _limiter


def reset_rate_limiter() -> None:
    """
    Test helper to ensure a fresh limiter instance is constructed after settings change.
    """

    global _limiter
    with _lock:
        _limiter = None


def _build_rate_limiter() -> RateLimiter:
    if not settings.RATE_LIMIT_ENABLED:
        logger.info("Rate limiting disabled via RATE_LIMIT_ENABLED=false; using NoopRateLimiter")
        return NoopRateLimiter()

    table_name = settings.DDB_RATE_LIMIT_TABLE
    region = settings.AWS_REGION
    if not table_name:
        logger.warning("RATE_LIMIT_ENABLED=true but DDB_RATE_LIMIT_TABLE is unset; disabling limiter")
        return NoopRateLimiter()
    if not region:
        logger.warning("RATE_LIMIT_ENABLED=true but AWS_REGION is unset; disabling limiter")
        return NoopRateLimiter()

    from app.services.rate_limiter_dynamo import DynamoRateLimiter

    client = boto3.client("dynamodb", region_name=region)
    logger.info("Rate limiting enabled using DynamoDB table %s in %s", table_name, region)
    return DynamoRateLimiter(client, table_name=table_name)

