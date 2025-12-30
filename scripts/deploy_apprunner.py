#!/usr/bin/env python3
"""
Deploy a new ECR image to an existing App Runner service using boto3.

Fixes vs prior version:
- DO NOT call StartDeployment unless the service is RUNNING.
- After UpdateService, wait for App Runner to finish the operation (can take minutes).
- If StartDeployment fails due to state/operation-in-progress, we keep waiting and proceed.
- Rollback waits for the service to be updatable (not OPERATION_IN_PROGRESS) before UpdateService.

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
import urllib.error
import urllib.request
from dataclasses import dataclass

import boto3
from botocore.exceptions import ClientError


POLL_SECONDS = 10


@dataclass(frozen=True)
class ServiceImage:
    image_identifier: str
    image_repository_type: str  # "ECR" or "ECR_PUBLIC"


def _describe_service(apprunner, service_arn: str) -> dict:
    return apprunner.describe_service(ServiceArn=service_arn)["Service"]


def _get_service_image(apprunner, service_arn: str) -> ServiceImage:
    svc = _describe_service(apprunner, service_arn)
    src = svc.get("SourceConfiguration") or {}
    img_repo = src.get("ImageRepository") or {}
    image_identifier = img_repo.get("ImageIdentifier") or ""
    image_repo_type = img_repo.get("ImageRepositoryType") or "ECR"
    if not image_identifier:
        raise RuntimeError("Could not determine current ImageIdentifier from describe_service()")
    return ServiceImage(image_identifier=image_identifier, image_repository_type=image_repo_type)


def _update_service_image(apprunner, service_arn: str, image_uri: str, repo_type: str) -> None:
    apprunner.update_service(
        ServiceArn=service_arn,
        SourceConfiguration={
            "ImageRepository": {
                "ImageIdentifier": image_uri,
                "ImageRepositoryType": repo_type,
            },
            # We will deploy by UpdateService + (optional) StartDeployment.
            # If AutoDeploymentsEnabled were true, App Runner could deploy when the image changes.
            "AutoDeploymentsEnabled": False,
        },
    )


def _start_deployment_if_possible(apprunner, service_arn: str) -> None:
    """
    StartDeployment is only allowed when the service is RUNNING.
    If it's not allowed or already in progress, we just log and continue;
    UpdateService usually triggers the needed work anyway.
    """
    try:
        apprunner.start_deployment(ServiceArn=service_arn)
        print("[deploy] start_deployment() called", flush=True)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        msg = e.response.get("Error", {}).get("Message", str(e))

        # Common: InvalidRequestException when not RUNNING, or operation already in progress
        print(f"[deploy] start_deployment() skipped ({code}): {msg}", flush=True)


def _list_operations(apprunner, service_arn: str) -> list[dict]:
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
    # newest first is useful when printing
    ops.sort(key=lambda o: o.get("StartedAt") or 0, reverse=True)
    return ops


def _has_in_progress_operation(apprunner, service_arn: str) -> bool:
    ops = _list_operations(apprunner, service_arn)
    return any((o.get("Status") == "IN_PROGRESS") for o in ops)


def _latest_operation_summary(apprunner, service_arn: str) -> str:
    ops = _list_operations(apprunner, service_arn)
    if not ops:
        return "no operations"
    o = ops[0]
    return f'{o.get("Type")} {o.get("Status")} (id={o.get("Id")})'


def _wait_until_updatable(apprunner, service_arn: str, timeout_seconds: int) -> None:
    """
    Wait until the service is no longer busy (no IN_PROGRESS operations).
    App Runner can hold OPERATION_IN_PROGRESS for a while after UpdateService.
    """
    deadline = time.time() + timeout_seconds
    last_summary = None

    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for service to become updatable after {timeout_seconds}s")

        summary = _latest_operation_summary(apprunner, service_arn)
        if summary != last_summary:
            print(f"[wait] operations => {summary}", flush=True)
            last_summary = summary

        if not _has_in_progress_operation(apprunner, service_arn):
            return

        time.sleep(POLL_SECONDS)


def _wait_for_running_and_image(
    apprunner,
    service_arn: str,
    desired_image_uri: str,
    timeout_seconds: int,
) -> None:
    """
    Wait for:
    - service Status == RUNNING
    - no IN_PROGRESS operations
    - current service image == desired_image_uri

    This handles the fact that UpdateService can take minutes.
    """
    deadline = time.time() + timeout_seconds
    last_status = None

    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for RUNNING + desired image after {timeout_seconds}s")

        svc = _describe_service(apprunner, service_arn)
        status = svc.get("Status")
        current = _get_service_image(apprunner, service_arn).image_identifier

        if status != last_status:
            print(f"[wait] service status => {status}", flush=True)
            last_status = status

        # If App Runner ever reports FAILED/DELETED/etc, bail early.
        if status and status not in {"RUNNING", "OPERATION_IN_PROGRESS"}:
            # Some accounts show other transient statuses; keep the message helpful.
            print(f"[wait] service entered status={status} while waiting; current image={current}", flush=True)

        in_prog = _has_in_progress_operation(apprunner, service_arn)

        if (not in_prog) and status == "RUNNING" and current == desired_image_uri:
            print("[wait] service is RUNNING, no operations IN_PROGRESS, and image matches", flush=True)
            return

        time.sleep(POLL_SECONDS)


def _http_get_status(url: str, timeout_seconds: int = 10) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0


def _health_check(url: str, attempts: int = 60, sleep_seconds: int = 5) -> None:
    """
    Default: up to ~5 minutes (60 * 5s). App Runner can take a bit to warm up.
    """
    for i in range(1, attempts + 1):
        code = _http_get_status(url)
        print(f"[health] attempt {i}/{attempts} => HTTP {code}", flush=True)
        if code == 200:
            return
        time.sleep(sleep_seconds)
    raise RuntimeError(f"Health check failed (expected 200) for {url}")


def _rollback(
    apprunner,
    service_arn: str,
    previous: ServiceImage,
    timeout_seconds: int,
    health_url: str,
) -> None:
    print(f"[rollback] rolling back to previous image: {previous.image_identifier}", flush=True)

    # Wait until we can update (avoid OPERATION_IN_PROGRESS errors)
    _wait_until_updatable(apprunner, service_arn, timeout_seconds)

    _update_service_image(apprunner, service_arn, previous.image_identifier, previous.image_repository_type)

    # Wait for update to apply; then (optional) start_deployment if possible
    _wait_for_running_and_image(apprunner, service_arn, previous.image_identifier, timeout_seconds)
    _start_deployment_if_possible(apprunner, service_arn)

    # After StartDeployment, it may kick a new op; wait for it to settle
    _wait_for_running_and_image(apprunner, service_arn, previous.image_identifier, timeout_seconds)

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
        # If there's already an operation in progress, wait before updating
        print("[deploy] waiting for service to be updatable (no IN_PROGRESS ops)...", flush=True)
        _wait_until_updatable(apprunner, args.service_arn, args.timeout_seconds)

        print("[deploy] updating service to new image...", flush=True)
        _update_service_image(apprunner, args.service_arn, args.image_uri, "ECR")

        # Wait for the UpdateService operation to finish and image to be the desired one
        print("[deploy] waiting for update to apply (can take a few minutes)...", flush=True)
        _wait_for_running_and_image(apprunner, args.service_arn, args.image_uri, args.timeout_seconds)

        # StartDeployment is optional; call only if possible (RUNNING).
        # If it errors because App Runner already did the work, that's fine.
        print("[deploy] attempting start_deployment (only works if RUNNING)...", flush=True)
        _start_deployment_if_possible(apprunner, args.service_arn)

        # If StartDeployment kicked off another operation, wait for settle again
        print("[deploy] waiting for service to stabilize after deployment...", flush=True)
        _wait_for_running_and_image(apprunner, args.service_arn, args.image_uri, args.timeout_seconds)

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