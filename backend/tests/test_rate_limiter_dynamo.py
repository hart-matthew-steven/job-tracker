from __future__ import annotations

import boto3
from botocore.stub import Stubber

from app.services.rate_limiter_dynamo import DynamoRateLimiter, OVERRIDE_SORT_KEY


def _client():
    return boto3.client("dynamodb", region_name="us-east-1")


def _override_get_item_params(identifier: str):
    return {
        "TableName": "jobapptracker-rate-limits",
        "Key": {"pk": {"S": identifier}, "sk": {"S": OVERRIDE_SORT_KEY}},
        "ConsistentRead": True,
    }


def test_allows_requests_within_limit():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 100
    window_seconds = 60
    window_start = 60
    expires_at = window_start + window_seconds + 5

    stubber.add_response("get_item", {}, _override_get_item_params("user:1"))
    expected_params = {
        "TableName": "jobapptracker-rate-limits",
        "Key": {"pk": {"S": "user:1"}, "sk": {"S": "route:test_window:window:60"}},
        "UpdateExpression": (
            "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
            "expires_at = :expires_at, #window_seconds = :window_seconds, #request_limit = :request_limit, "
            "#route_key = :route_key, #item_type = :item_type"
        ),
        "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
        "ExpressionAttributeNames": {
            "#count": "count",
            "#window_seconds": "window_seconds",
            "#request_limit": "request_limit",
            "#route_key": "route_key",
            "#item_type": "item_type",
        },
        "ExpressionAttributeValues": {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
            ":window_seconds": {"N": str(window_seconds)},
            ":request_limit": {"N": "5"},
            ":route_key": {"S": "test_window"},
            ":item_type": {"S": "counter"},
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
                "window_seconds": {"N": str(window_seconds)},
                "request_limit": {"N": "5"},
                "route_key": {"S": "test_window"},
                "item_type": {"S": "counter"},
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
    assert result.count == 1
    assert result.limiter_key == "route:test_window:window:60"


def test_blocks_when_limit_exceeded():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 130
    window_seconds = 60
    window_start = 120
    expires_at = window_start + window_seconds + 5

    stubber.add_response("get_item", {}, _override_get_item_params("user:1"))
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "11"},
                "window_start": {"N": str(window_start)},
                "expires_at": {"N": str(expires_at)},
                "window_seconds": {"N": str(window_seconds)},
                "request_limit": {"N": "10"},
                "route_key": {"S": "ai_chat"},
                "item_type": {"S": "counter"},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:1"}, "sk": {"S": "route:ai_chat:window:60"}},
            "UpdateExpression": (
                "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                "expires_at = :expires_at, #window_seconds = :window_seconds, #request_limit = :request_limit, "
                "#route_key = :route_key, #item_type = :item_type"
            ),
            "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
            "ExpressionAttributeNames": {
                "#count": "count",
                "#window_seconds": "window_seconds",
                "#request_limit": "request_limit",
                "#route_key": "route_key",
                "#item_type": "item_type",
            },
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":expires_at": {"N": str(expires_at)},
                ":inc": {"N": "1"},
                ":zero": {"N": "0"},
                ":window_seconds": {"N": str(window_seconds)},
                ":request_limit": {"N": "10"},
                ":route_key": {"S": "ai_chat"},
                ":item_type": {"S": "counter"},
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
    assert result.count == 11


def test_resets_counter_when_window_rolls_over():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 181
    window_seconds = 60
    window_start = 180
    expires_at = window_start + window_seconds + 5

    stubber.add_response("get_item", {}, _override_get_item_params("user:99"))

    first_params = {
        "TableName": "jobapptracker-rate-limits",
        "Key": {"pk": {"S": "user:99"}, "sk": {"S": "route:ai_conversations:window:60"}},
        "UpdateExpression": (
            "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
            "expires_at = :expires_at, #window_seconds = :window_seconds, #request_limit = :request_limit, "
            "#route_key = :route_key, #item_type = :item_type"
        ),
        "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
        "ExpressionAttributeNames": {
            "#count": "count",
            "#window_seconds": "window_seconds",
            "#request_limit": "request_limit",
            "#route_key": "route_key",
            "#item_type": "item_type",
        },
        "ExpressionAttributeValues": {
            ":window_start": {"N": str(window_start)},
            ":expires_at": {"N": str(expires_at)},
            ":inc": {"N": "1"},
            ":zero": {"N": "0"},
            ":window_seconds": {"N": str(window_seconds)},
            ":request_limit": {"N": "5"},
            ":route_key": {"S": "ai_conversations"},
            ":item_type": {"S": "counter"},
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
                "window_seconds": {"N": str(window_seconds)},
                "request_limit": {"N": "5"},
                "route_key": {"S": "ai_conversations"},
                "item_type": {"S": "counter"},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:99"}, "sk": {"S": "route:ai_conversations:window:60"}},
            "UpdateExpression": (
                "SET window_start = :window_start, #count = :one, expires_at = :expires_at, "
                "#window_seconds = :window_seconds, #request_limit = :request_limit, "
                "#route_key = :route_key, #item_type = :item_type"
            ),
            "ExpressionAttributeNames": {
                "#count": "count",
                "#window_seconds": "window_seconds",
                "#request_limit": "request_limit",
                "#route_key": "route_key",
                "#item_type": "item_type",
            },
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":one": {"N": "1"},
                ":expires_at": {"N": str(expires_at)},
                ":window_seconds": {"N": str(window_seconds)},
                ":request_limit": {"N": "5"},
                ":route_key": {"S": "ai_conversations"},
                ":item_type": {"S": "counter"},
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


def test_override_honored_until_ttl():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 200
    override_window = 30
    window_start = 180
    expires_at = window_start + override_window + 5

    stubber.add_response(
        "get_item",
        {
            "Item": {
                "request_limit": {"N": "20"},
                "window_seconds": {"N": str(override_window)},
                "expires_at": {"N": "500"},
            }
        },
        _override_get_item_params("user:2"),
    )
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "3"},
                "request_limit": {"N": "20"},
                "window_seconds": {"N": str(override_window)},
                "route_key": {"S": "ai_chat"},
                "item_type": {"S": "counter"},
                "expires_at": {"N": str(expires_at)},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:2"}, "sk": {"S": f"route:ai_chat:window:{override_window}"}},
            "UpdateExpression": (
                "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                "expires_at = :expires_at, #window_seconds = :window_seconds, #request_limit = :request_limit, "
                "#route_key = :route_key, #item_type = :item_type"
            ),
            "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
            "ExpressionAttributeNames": {
                "#count": "count",
                "#window_seconds": "window_seconds",
                "#request_limit": "request_limit",
                "#route_key": "route_key",
                "#item_type": "item_type",
            },
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":expires_at": {"N": str(expires_at)},
                ":inc": {"N": "1"},
                ":zero": {"N": "0"},
                ":window_seconds": {"N": str(override_window)},
                ":request_limit": {"N": "20"},
                ":route_key": {"S": "ai_chat"},
                ":item_type": {"S": "counter"},
            },
            "ReturnValues": "ALL_NEW",
        },
    )

    with stubber:
        result = limiter.check(
            identifier="user:2",
            route_key="ai_chat",
            limit=5,
            window_seconds=60,
            now=now,
        )

    assert result.limit == 20
    assert result.window_seconds == override_window
    assert result.remaining == 17
    assert result.allowed


def test_override_expired_is_ignored():
    client = _client()
    limiter = DynamoRateLimiter(client, table_name="jobapptracker-rate-limits", ttl_buffer_seconds=5)
    stubber = Stubber(client)

    now = 600
    window_seconds = 60
    window_start = 600
    expires_at = window_start + window_seconds + 5

    stubber.add_response(
        "get_item",
        {
            "Item": {
                "request_limit": {"N": "50"},
                "window_seconds": {"N": "30"},
                "expires_at": {"N": "500"},
            }
        },
        _override_get_item_params("user:5"),
    )
    stubber.add_response(
        "delete_item",
        {},
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:5"}, "sk": {"S": OVERRIDE_SORT_KEY}},
        },
    )
    stubber.add_response(
        "update_item",
        {
            "Attributes": {
                "count": {"N": "1"},
                "request_limit": {"N": "5"},
                "window_seconds": {"N": str(window_seconds)},
                "route_key": {"S": "ai_chat"},
                "item_type": {"S": "counter"},
                "expires_at": {"N": str(expires_at)},
            }
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "Key": {"pk": {"S": "user:5"}, "sk": {"S": f"route:ai_chat:window:{window_seconds}"}},
            "UpdateExpression": (
                "SET window_start = :window_start, #count = if_not_exists(#count, :zero) + :inc, "
                "expires_at = :expires_at, #window_seconds = :window_seconds, #request_limit = :request_limit, "
                "#route_key = :route_key, #item_type = :item_type"
            ),
            "ConditionExpression": "attribute_not_exists(window_start) OR window_start = :window_start",
            "ExpressionAttributeNames": {
                "#count": "count",
                "#window_seconds": "window_seconds",
                "#request_limit": "request_limit",
                "#route_key": "route_key",
                "#item_type": "item_type",
            },
            "ExpressionAttributeValues": {
                ":window_start": {"N": str(window_start)},
                ":expires_at": {"N": str(expires_at)},
                ":inc": {"N": "1"},
                ":zero": {"N": "0"},
                ":window_seconds": {"N": str(window_seconds)},
                ":request_limit": {"N": "5"},
                ":route_key": {"S": "ai_chat"},
                ":item_type": {"S": "counter"},
            },
            "ReturnValues": "ALL_NEW",
        },
    )

    with stubber:
        result = limiter.check(
            identifier="user:5",
            route_key="ai_chat",
            limit=5,
            window_seconds=window_seconds,
            now=now,
        )

    assert result.limit == 5
    assert result.window_seconds == window_seconds
    assert result.remaining == 4

