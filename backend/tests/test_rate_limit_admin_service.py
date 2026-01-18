from __future__ import annotations

import boto3
from botocore.stub import Stubber

from app.core import config as app_config
from app.services.rate_limit_admin import RateLimitAdminService


def _service_and_stubber():
    client = boto3.client("dynamodb", region_name="us-east-1")
    stubber = Stubber(client)
    previous = app_config.settings.DDB_RATE_LIMIT_TABLE
    app_config.settings.DDB_RATE_LIMIT_TABLE = "jobapptracker-rate-limits"
    try:
        service = RateLimitAdminService(client=client)
    finally:
        app_config.settings.DDB_RATE_LIMIT_TABLE = previous
    return service, stubber


def test_list_user_limits_filters_expired():
    service, stubber = _service_and_stubber()
    response = {
        "Items": [
            {
                "pk": {"S": "user:7"},
                "sk": {"S": "route:ai_chat:window:60"},
                "count": {"N": "3"},
                "request_limit": {"N": "10"},
                "window_seconds": {"N": "60"},
                "expires_at": {"N": "1000"},
            },
            {
                "pk": {"S": "user:7"},
                "sk": {"S": "route:ai_chat:window:60"},
                "count": {"N": "5"},
                "request_limit": {"N": "10"},
                "expires_at": {"N": "50"},
            },
        ]
    }
    stubber.add_response(
        "query",
        response,
        {
            "TableName": "jobapptracker-rate-limits",
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": {"S": "user:7"}},
        },
    )

    with stubber:
        records = service.list_user_limits(user_id=7, now=200)

    assert len(records) == 1
    assert records[0].limiter_key == "route:ai_chat:window:60"
    assert records[0].remaining == 7


def test_reset_user_limits_deletes_all_items():
    service, stubber = _service_and_stubber()
    stubber.add_response(
        "query",
        {
            "Items": [
                {"pk": {"S": "user:9"}, "sk": {"S": "route:ai_chat:window:60"}},
                {"pk": {"S": "user:9"}, "sk": {"S": "override:global"}},
            ]
        },
        {
            "TableName": "jobapptracker-rate-limits",
            "KeyConditionExpression": "pk = :pk",
            "ExpressionAttributeValues": {":pk": {"S": "user:9"}},
            "ProjectionExpression": "pk, sk",
        },
    )
    stubber.add_response(
        "batch_write_item",
        {"UnprocessedItems": {}},
        {
            "RequestItems": {
                "jobapptracker-rate-limits": [
                    {"DeleteRequest": {"Key": {"pk": {"S": "user:9"}, "sk": {"S": "route:ai_chat:window:60"}}}},
                    {"DeleteRequest": {"Key": {"pk": {"S": "user:9"}, "sk": {"S": "override:global"}}}},
                ]
            }
        },
    )

    with stubber:
        deleted = service.reset_user_limits(user_id=9)

    assert deleted == 2


def test_apply_override_writes_ttl():
    service, stubber = _service_and_stubber()
    stubber.add_response(
        "put_item",
        {},
        {
            "TableName": "jobapptracker-rate-limits",
            "Item": {
                "pk": {"S": "user:4"},
                "sk": {"S": "override:global"},
                "request_limit": {"N": "25"},
                "window_seconds": {"N": "30"},
                "expires_at": {"N": "230"},
                "item_type": {"S": "override"},
            },
        },
    )

    with stubber:
        expires = service.apply_override(user_id=4, limit=25, window_seconds=30, ttl_seconds=200, now=30)

    assert expires == 230
