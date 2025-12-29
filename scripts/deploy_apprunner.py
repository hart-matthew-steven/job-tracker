#!/usr/bin/env python3
"""
Deploy a new ECR image to an existing App Runner service using boto3.

Features:
- Captures the currently deployed image for rollback
- Updates service image to the new image URI
- Starts deployment
- Waits until deployment completes (no IN_PROGRESS operations)
- Performs a health check (expects HTTP 200)
- Rolls back to previous image on failure

Usage:
  python scripts/deploy_apprunner.py \
    --region us-east-1 \
    --service-arn arn:aws:apprunner:... \
    --image-uri 123456789012.dkr.ecr.us-east-1.amazonaws.com/repo:tag \
    --health-url https://api.example.com/health \
    --timeout-seconds 900
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass

import boto3


@dataclass(frozen=True)
class ServiceImage:
    image_identifier: str
    image_repository_type: str  # "ECR" or "ECR_PUBLIC"


def _get_service_image(apprunner, service_arn: str) -> ServiceImage:
    resp = apprunner.describe_service(ServiceArn=service_arn)
    svc = resp["Service"]
    src = svc.get("SourceConfiguration") or {}
    img_repo = src.get("ImageRepository") or {}
    image_identifier = img_repo.get("ImageIdentifier") or ""
    image_repo_type = img_repo.get("ImageRepositoryType") or "ECR"
    if not image_identifier:
        raise RuntimeError("Could not determine current ImageIdentifier from describe_service()")
    return ServiceImage(image_identifier=image_identifier, image_repository_type=image_repo_type)


def _update_service_image(apprunner, service_arn: str, image_uri: str, repo_type: str) -> None:
    # Keep config minimal and explicit.
    # AutoDeploymentsEnabled false: we control deployments manually via start_deployment.
    apprunner.update_service(
        ServiceArn=service_arn,
        SourceConfiguration={
            "ImageRepository": {
                "ImageIdentifier": image_uri,
                "ImageRepositoryType": repo_type,  # usually "ECR"
            },
            "AutoDeploymentsEnabled": False,
        },
    )


def _start_deployment(apprunner, service_arn: str) -> None:
    apprunner.start_deployment(ServiceArn=service_arn)


def _list_in_progress_operations(apprunner, service_arn: str) -> list[dict]:
    # If there is an ongoing deploy/update, App Runner tracks it as an operation.
    # We'll poll until there are no IN_PROGRESS operations.
    ops: list[dict] = []
    next_token = None
    while True:
        kwargs = {"ServiceArn": service_arn, "MaxResults": 50}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = apprunner.list_operations(**kwargs)
        ops.extend(resp.get("OperationSummaryList") or [])
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return [o for o in ops if (o.get("Status") == "IN_PROGRESS")]


def _wait_for_stable(apprunner, service_arn: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_status = None

    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for deployment to stabilize after {timeout_seconds}s")

        svc = apprunner.describe_service(ServiceArn=service_arn)["Service"]
        status = svc.get("Status")
        if status != last_status:
            print(f"[wait] service status => {status}", flush=True)
            last_status = status

        in_progress = _list_in_progress_operations(apprunner, service_arn)
        if not in_progress and status == "RUNNING":
            print("[wait] service is RUNNING and no operations are IN_PROGRESS", flush=True)
            return

        time.sleep(10)


def _http_get_status(url: str, timeout_seconds: int = 10) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0


def _health_check(url: str, attempts: int = 12, sleep_seconds: int = 5) -> None:
    # up to ~1 minute total by default
    for i in range(1, attempts + 1):
        code = _http_get_status(url)
        print(f"[health] attempt {i}/{attempts} => HTTP {code}", flush=True)
        if code == 200:
            return
        time.sleep(sleep_seconds)
    raise RuntimeError(f"Health check failed (expected 200) for {url}")


def _rollback(apprunner, service_arn: str, previous: ServiceImage, timeout_seconds: int, health_url: str) -> None:
    print(f"[rollback] rolling back to previous image: {previous.image_identifier}", flush=True)
    _update_service_image(apprunner, service_arn, previous.image_identifier, previous.image_repository_type)
    _start_deployment(apprunner, service_arn)
    _wait_for_stable(apprunner, service_arn, timeout_seconds)
    _health_check(health_url)
    print("[rollback] rollback complete and health check passed", flush=True)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--service-arn", required=True)
    p.add_argument("--image-uri", required=True)
    p.add_argument("--health-url", required=True)
    p.add_argument("--timeout-seconds", type=int, default=900)  # 15 minutes
    args = p.parse_args()

    apprunner = boto3.client("apprunner", region_name=args.region)

    print("[deploy] resolving currently deployed image...", flush=True)
    previous = _get_service_image(apprunner, args.service_arn)
    print(f"[deploy] previous image => {previous.image_identifier}", flush=True)
    print(f"[deploy] new image      => {args.image_uri}", flush=True)

    try:
        print("[deploy] updating service to new image...", flush=True)
        _update_service_image(apprunner, args.service_arn, args.image_uri, "ECR")

        print("[deploy] starting deployment...", flush=True)
        _start_deployment(apprunner, args.service_arn)

        print("[deploy] waiting for service to stabilize...", flush=True)
        _wait_for_stable(apprunner, args.service_arn, args.timeout_seconds)

        print("[deploy] running health check...", flush=True)
        _health_check(args.health_url)

        print("[deploy] ✅ deployment succeeded and health check passed", flush=True)
        return 0

    except Exception as e:
        print(f"[deploy] ❌ deployment failed: {e}", file=sys.stderr, flush=True)
        try:
            _rollback(apprunner, args.service_arn, previous, args.timeout_seconds, args.health_url)
            print("[deploy] ✅ rollback succeeded", flush=True)
        except Exception as re:
            print(f"[deploy] ❌ rollback failed: {re}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())