from __future__ import annotations

import logging

from celery import Celery

from app.core.config import settings


logger = logging.getLogger(__name__)

BROKER_CONFIGURED = bool(settings.AI_ARTIFACTS_SQS_QUEUE_URL)

if BROKER_CONFIGURED and not settings.AWS_REGION:
    logger.warning("AI artifacts queue configured but AWS_REGION missing; defaulting to us-east-1")

celery_app = Celery("jobtracker-artifacts")

if BROKER_CONFIGURED:
    broker_url = "sqs://"
    broker_options = {
        "region": settings.AWS_REGION or "us-east-1",
        "visibility_timeout": 60 * 30,
        "queue_name_prefix": "",
        "predefined_queues": {
            "artifact-tasks": {
                "url": settings.AI_ARTIFACTS_SQS_QUEUE_URL,
            }
        },
    }
else:
    broker_url = "memory://"
    broker_options = {}
    logger.warning("AI_ARTIFACTS_SQS_QUEUE_URL is not configured; Celery will run in in-memory mode.")

celery_app.conf.update(
    broker_url=broker_url,
    result_backend=None,
    task_default_queue="artifact-tasks",
    task_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
    timezone="UTC",
    enable_utc=True,
)

if broker_options:
    celery_app.conf.broker_transport_options = broker_options


def enqueue(task, *args, **kwargs):
    """
    Convenience helper so the API can enqueue tasks without caring
    whether the broker is configured. In tests/local dev we execute tasks inline.
    """
    if BROKER_CONFIGURED:
        return task.delay(*args, **kwargs)
    logger.info("Celery broker not configured; running %s synchronously", task.name)
    return task.apply(args=args, kwargs=kwargs)
