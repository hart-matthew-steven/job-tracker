from __future__ import annotations

import time
from dataclasses import dataclass

from botocore.exceptions import ClientError
from botocore.client import BaseClient

from app.services.rate_limiter import RateLimitResult, RateLimiter


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
        if limit <= 0:
            return RateLimitResult(allowed=True, retry_after_seconds=0, limit=limit, remaining=0)

        now_ts = int(now or time.time())
        window_start = now_ts - (now_ts % window_seconds)
        key = self._build_key(route_key, window_seconds)
        expires_at = window_start + window_seconds + self.ttl_buffer_seconds

        attributes = self._increment_window(
            key=key,
            identifier=identifier,
            window_start=window_start,
            expires_at=expires_at,
        )

        count = int(attributes.get("count", {}).get("N", "0"))
        remaining = max(0, limit - count)
        allowed = count <= limit
        retry_after = 0
        if not allowed:
            retry_after = max(1, window_start + window_seconds - now_ts)

        return RateLimitResult(
            allowed=allowed,
            retry_after_seconds=retry_after,
            limit=limit,
            remaining=remaining,
        )

    def _increment_window(
        self,
        *,
        key: str,
        identifier: str,
        window_start: int,
        expires_at: int,
    ) -> dict:
        item_key = {"pk": {"S": identifier}, "sk": {"S": key}}
        expression_names = {"#count": "count"}
        expression_values = {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
        }

        try:
            response = self.client.update_item(
                TableName=self.table_name,
                Key=item_key,
                UpdateExpression=(
                    "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                    "expires_at = :expires_at"
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
            )

    def _reset_window(
        self,
        *,
        item_key: dict,
        window_start: int,
        expires_at: int,
    ) -> dict:
        response = self.client.update_item(
            TableName=self.table_name,
            Key=item_key,
            UpdateExpression="SET window_start = :window_start, #count = :one, expires_at = :expires_at",
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={
                ":window_start": {"N": str(window_start)},
                ":one": {"N": "1"},
                ":expires_at": {"N": str(expires_at)},
            },
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    @staticmethod
    def _build_key(route_key: str, window_seconds: int) -> str:
        return f"route:{route_key}:window:{window_seconds}"

