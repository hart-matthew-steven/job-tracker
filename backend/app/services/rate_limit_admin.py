from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Iterable

import boto3
from botocore.client import BaseClient

from app.core.config import settings
from app.services.rate_limiter_dynamo import OVERRIDE_SORT_KEY


class RateLimitAdminError(RuntimeError):
    pass


@dataclass(frozen=True)
class RateLimitRecord:
    limiter_key: str
    window_seconds: int
    limit: int
    count: int
    remaining: int
    expires_at: int
    record_type: str


class RateLimitAdminService:
    def __init__(
        self,
        *,
        client: BaseClient | None = None,
        table_name: str | None = None,
    ) -> None:
        self.table_name = (table_name or settings.DDB_RATE_LIMIT_TABLE or "").strip()
        if not self.table_name:
            raise RateLimitAdminError("DDB_RATE_LIMIT_TABLE is not configured")
        region = (settings.AWS_REGION or "").strip()
        if not region and client is None:
            raise RateLimitAdminError("AWS_REGION is not configured")
        self.client: BaseClient = client or boto3.client("dynamodb", region_name=region)

    def list_user_limits(self, *, user_id: int, now: int | None = None) -> List[RateLimitRecord]:
        pk = self._pk(user_id)
        response = self.client.query(
            TableName=self.table_name,
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": {"S": pk}},
        )
        items = response.get("Items", [])
        now_ts = int(now or time.time())
        records: list[RateLimitRecord] = []
        for item in items:
            expires_at = self._as_int(item.get("expires_at"), default=0)
            if expires_at and expires_at <= now_ts:
                continue
            records.append(self._normalize_record(item))
        return records

    def reset_user_limits(self, *, user_id: int) -> int:
        pk = self._pk(user_id)
        response = self.client.query(
            TableName=self.table_name,
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": {"S": pk}},
            ProjectionExpression="pk, sk",
        )
        items = response.get("Items", [])
        if not items:
            return 0

        total_deleted = 0
        for chunk in _chunks(items, 25):
            requests = [
                {"DeleteRequest": {"Key": {"pk": {"S": pk}, "sk": item["sk"]}}}
                for item in chunk
            ]
            self.client.batch_write_item(RequestItems={self.table_name: requests})
            total_deleted += len(chunk)
        return total_deleted

    def apply_override(
        self,
        *,
        user_id: int,
        limit: int,
        window_seconds: int,
        ttl_seconds: int,
        now: int | None = None,
    ) -> int:
        if limit <= 0:
            raise RateLimitAdminError("limit must be greater than zero")
        if window_seconds <= 0:
            raise RateLimitAdminError("window_seconds must be greater than zero")
        if ttl_seconds <= 0:
            raise RateLimitAdminError("ttl_seconds must be greater than zero")

        pk = self._pk(user_id)
        now_ts = int(now or time.time())
        expires_at = now_ts + ttl_seconds

        self.client.put_item(
            TableName=self.table_name,
            Item={
                "pk": {"S": pk},
                "sk": {"S": OVERRIDE_SORT_KEY},
                "request_limit": {"N": str(limit)},
                "window_seconds": {"N": str(window_seconds)},
                "expires_at": {"N": str(expires_at)},
                "item_type": {"S": "override"},
            },
        )
        return expires_at

    def _pk(self, user_id: int) -> str:
        return f"user:{user_id}"

    def _normalize_record(self, item: dict[str, Any]) -> RateLimitRecord:
        limiter_key = item.get("sk", {}).get("S", "")
        record_type = item.get("item_type", {}).get("S", "counter")
        window_seconds = self._extract_window_seconds(item, limiter_key)
        limit = self._as_int(item.get("request_limit"), default=0)
        count = self._as_int(item.get("count"), default=0)
        expires_at = self._as_int(item.get("expires_at"), default=0)

        if record_type == "override":
            count = 0
            remaining = limit
        else:
            remaining = max(0, limit - count)

        return RateLimitRecord(
            limiter_key=limiter_key,
            window_seconds=window_seconds,
            limit=limit,
            count=count,
            remaining=remaining,
            expires_at=expires_at,
            record_type=record_type,
        )

    @staticmethod
    def _extract_window_seconds(item: dict[str, Any], limiter_key: str) -> int:
        explicit = item.get("window_seconds")
        if explicit and "N" in explicit:
            return int(explicit["N"])
        if "window:" in limiter_key:
            try:
                return int(limiter_key.rsplit("window:", 1)[1])
            except (IndexError, ValueError):
                return 0
        return 0

    @staticmethod
    def _as_int(value: dict[str, str] | None, *, default: int) -> int:
        if not value:
            return default
        return int(value.get("N", default) or default)


def _chunks(items: Iterable[Any], size: int) -> Iterable[list[Any]]:
    chunk: list[Any] = []
    for item in items:
        chunk.append(item)
        if len(chunk) == size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
