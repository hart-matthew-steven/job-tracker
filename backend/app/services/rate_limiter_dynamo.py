from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from botocore.client import BaseClient
from botocore.exceptions import ClientError

from app.services.rate_limiter import RateLimitResult, RateLimiter


OVERRIDE_SORT_KEY = "override:global"


@dataclass(frozen=True)
class DynamoRateLimiter(RateLimiter):
    client: BaseClient
    table_name: str
    ttl_buffer_seconds: int = 5

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
        override = self._get_override(identifier=identifier, now_ts=now_ts)
        effective_limit = override["limit"] if override else limit
        effective_window = override["window_seconds"] if override else window_seconds
        limiter_key = self._build_key(route_key, effective_window)

        if effective_limit <= 0 or effective_window <= 0:
            reset_epoch = now_ts + max(effective_window, 0)
            return RateLimitResult(
                allowed=True,
                retry_after_seconds=0,
                limit=effective_limit,
                remaining=0,
                count=0,
                window_reset_epoch=reset_epoch,
                limiter_key=limiter_key,
                window_seconds=effective_window,
            )

        window_start = now_ts - (now_ts % effective_window)
        expires_at = window_start + effective_window + self.ttl_buffer_seconds

        attributes = self._increment_window(
            key=limiter_key,
            identifier=identifier,
            window_start=window_start,
            expires_at=expires_at,
            route_key=route_key,
            limit=effective_limit,
            window_seconds=effective_window,
        )

        count = int(attributes.get("count", {}).get("N", "0"))
        remaining = max(0, effective_limit - count)
        allowed = count <= effective_limit
        retry_after = 0
        if not allowed:
            retry_after = max(1, window_start + effective_window - now_ts)

        return RateLimitResult(
            allowed=allowed,
            retry_after_seconds=retry_after,
            limit=effective_limit,
            remaining=remaining,
            count=count,
            window_reset_epoch=window_start + effective_window,
            limiter_key=limiter_key,
            window_seconds=effective_window,
        )

    def _increment_window(
        self,
        *,
        key: str,
        identifier: str,
        window_start: int,
        expires_at: int,
        route_key: str,
        limit: int,
        window_seconds: int,
    ) -> dict[str, Any]:
        item_key = {"pk": {"S": identifier}, "sk": {"S": key}}
        expression_names = {
            "#count": "count",
            "#window_seconds": "window_seconds",
            "#request_limit": "request_limit",
            "#route_key": "route_key",
            "#item_type": "item_type",
        }
        expression_values = {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
            ":window_seconds": {"N": str(window_seconds)},
            ":request_limit": {"N": str(limit)},
            ":route_key": {"S": route_key},
            ":item_type": {"S": "counter"},
        }

        try:
            response = self.client.update_item(
                TableName=self.table_name,
                Key=item_key,
                UpdateExpression=(
                    "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                    "expires_at = :expires_at, #window_seconds = :window_seconds, "
                    "#request_limit = :request_limit, #route_key = :route_key, #item_type = :item_type"
                ),
                ConditionExpression="attribute_not_exists(window_start) OR window_start = :window_start",
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
                ReturnValues="ALL_NEW",
            )
            return response.get("Attributes", {})
        except ClientError as err:
            if err.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
            return self._reset_window(
                item_key=item_key,
                window_start=window_start,
                expires_at=expires_at,
                route_key=route_key,
                limit=limit,
                window_seconds=window_seconds,
            )

    def _reset_window(
        self,
        *,
        item_key: dict[str, Any],
        window_start: int,
        expires_at: int,
        route_key: str,
        limit: int,
        window_seconds: int,
    ) -> dict[str, Any]:
        response = self.client.update_item(
            TableName=self.table_name,
            Key=item_key,
            UpdateExpression=(
                "SET window_start = :window_start, #count = :one, expires_at = :expires_at, "
                "#window_seconds = :window_seconds, #request_limit = :request_limit, "
                "#route_key = :route_key, #item_type = :item_type"
            ),
            ExpressionAttributeNames={
                "#count": "count",
                "#window_seconds": "window_seconds",
                "#request_limit": "request_limit",
                "#route_key": "route_key",
                "#item_type": "item_type",
            },
            ExpressionAttributeValues={
                ":window_start": {"N": str(window_start)},
                ":one": {"N": "1"},
                ":expires_at": {"N": str(expires_at)},
                ":window_seconds": {"N": str(window_seconds)},
                ":request_limit": {"N": str(limit)},
                ":route_key": {"S": route_key},
                ":item_type": {"S": "counter"},
            },
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    @staticmethod
    def _build_key(route_key: str, window_seconds: int) -> str:
        return f"route:{route_key}:window:{window_seconds}"

    def _get_override(self, *, identifier: str, now_ts: int) -> dict[str, int] | None:
        response = self.client.get_item(
            TableName=self.table_name,
            Key={"pk": {"S": identifier}, "sk": {"S": OVERRIDE_SORT_KEY}},
            ConsistentRead=True,
        )
        item = response.get("Item")
        if not item:
            return None

        expires_at = int(item.get("expires_at", {}).get("N", "0"))
        if expires_at and expires_at <= now_ts:
            self._delete_override(identifier=identifier)
            return None

        limit = int(item.get("request_limit", {}).get("N", "0"))
        window_seconds = int(item.get("window_seconds", {}).get("N", "0"))
        if limit <= 0 or window_seconds <= 0:
            return None
        return {"limit": limit, "window_seconds": window_seconds, "expires_at": expires_at}

    def _delete_override(self, *, identifier: str) -> None:
        self.client.delete_item(
            TableName=self.table_name,
            Key={"pk": {"S": identifier}, "sk": {"S": OVERRIDE_SORT_KEY}},
        )
