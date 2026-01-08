from __future__ import annotations

import boto3
from botocore.stub import Stubber

from app.services.rate_limiter_dynamo import DynamoRateLimiter


def _client():
    return boto3.client("dynamodb", region_name="us-east-1")


def test_allows_requests_within_limit():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 100
    window_seconds = 60
    window_start = 60
    expires_at = window_start + window_seconds + 5
    expected_params = {
        "TableName": "jobapptracker-rate-limits",
        "Key": {"pk": {"S": "user:1"}, "sk": {"S": "route:test_window:window:60"}},
        "UpdateExpression": (
            "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
            "expires_at = :expires_at"
        ),
        "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
        "ExpressionAttributeNames": {"#count": "count"},
        "ExpressionAttributeValues": {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
        },
        "ReturnValues": "ALL_NEW",
    }
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "1"},
                "window_start": {"N": str(window_start)},
                "expires_at": {"N": str(expires_at)},
            }
        },
        expected_params,
    )

    with stubber:
        result = limiter.check(
            identifier="user:1",
            route_key="test_window",
            limit=5,
            window_seconds=window_seconds,
            now=now,
        )

    assert result.allowed
    assert result.remaining == 4
    assert result.retry_after_seconds == 0


def test_blocks_when_limit_exceeded():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 130
    window_seconds = 60
    window_start = 120
    expires_at = window_start + window_seconds + 5

    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "11"},
                "window_start": {"N": str(window_start)},
                "expires_at": {"N": str(expires_at)},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:1"}, "sk": {"S": "route:ai_chat:window:60"}},
            "UpdateExpression": (
                "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                "expires_at = :expires_at"
            ),
            "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
            "ExpressionAttributeNames": {"#count": "count"},
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":expires_at": {"N": str(expires_at)},
                ":inc": {"N": "1"},
                ":zero": {"N": "0"},
            },
            "ReturnValues": "ALL_NEW",
        },
    )

    with stubber:
        result = limiter.check(
            identifier="user:1",
            route_key="ai_chat",
            limit=10,
            window_seconds=window_seconds,
            now=now,
        )

    assert not result.allowed
    assert result.retry_after_seconds == max(1, window_start + window_seconds - now)
    assert result.remaining == 0


def test_resets_counter_when_window_rolls_over():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 181
    window_seconds = 60
    window_start = 180
    expires_at = window_start + window_seconds + 5

    first_params = {
        "TableName": "jobapptracker-rate-limits",
        "Key": {"pk": {"S": "user:99"}, "sk": {"S": "route:ai_conversations:window:60"}},
        "UpdateExpression": (
            "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
            "expires_at = :expires_at"
        ),
        "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
        "ExpressionAttributeNames": {"#count": "count"},
        "ExpressionAttributeValues": {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
        },
        "ReturnValues": "ALL_NEW",
    }
    stubber.add_client_error(
        "update_item",
        service_error_code="ConditionalCheckFailedException",
        service_message="stale window",
        expected_params=first_params,
    )
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "1"},
                "window_start": {"N": str(window_start)},
                "expires_at": {"N": str(expires_at)},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:99"}, "sk": {"S": "route:ai_conversations:window:60"}},
            "UpdateExpression": "SET window_start = :window_start, #count = :one, expires_at = :expires_at",
            "ExpressionAttributeNames": {"#count": "count"},
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":one": {"N": "1"},
                ":expires_at": {"N": str(expires_at)},
            },
            "ReturnValues": "ALL_NEW",
        },
    )

    with stubber:
        result = limiter.check(
            identifier="user:99",
            route_key="ai_conversations",
            limit=5,
            window_seconds=window_seconds,
            now=now,
        )

    assert result.allowed
    assert result.remaining == 4
    assert result.retry_after_seconds == 0

