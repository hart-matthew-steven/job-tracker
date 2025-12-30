#!/usr/bin/env python3
"""
Deploy static frontend assets to S3 + invalidate CloudFront.

Features:
- Uploads files from build dir to S3 with reasonable Cache-Control:
  - HTML: no-cache (so new deployments are picked up quickly)
  - Everything else: long cache (immutable-ish asset hashing is assumed)
- Deletes S3 objects that no longer exist in build output (sync --delete behavior)
- Creates CloudFront invalidation (default: /*)
- Optionally waits for invalidation completion

Usage:
  python scripts/deploy_frontend.py \
    --region us-east-1 \
    --bucket jobapptracker.dev \
    --distribution-id E1MVFELWUF5YFH \
    --build-dir frontend-web/dist \
    --invalidate-paths "/*" \
    --wait-invalidation
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import boto3


HTML_CACHE_CONTROL = "no-cache, no-store, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"


@dataclass(frozen=True)
class UploadSpec:
    key: str
    path: Path
    content_type: str | None
    cache_control: str


def _iter_local_files(build_dir: Path) -> Iterable[UploadSpec]:
    for p in build_dir.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(build_dir).as_posix()
        # S3 keys should never start with "./"
        key = rel.lstrip("./")

        content_type, _ = mimetypes.guess_type(str(p))
        # Cache policy:
        # - HTML should not be aggressively cached (helps rollouts)
        # - assets (js/css/images/etc) can be long cached
        if key.endswith(".html"):
            cache_control = HTML_CACHE_CONTROL
        else:
            cache_control = ASSET_CACHE_CONTROL

        yield UploadSpec(
            key=key,
            path=p,
            content_type=content_type,
            cache_control=cache_control,
        )


def _list_s3_keys(s3, bucket: str) -> set[str]:
    keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []) or []:
            k = obj.get("Key")
            if k:
                keys.add(k)
    return keys


def _upload_file(s3, bucket: str, spec: UploadSpec) -> None:
    extra_args = {"CacheControl": spec.cache_control}
    if spec.content_type:
        extra_args["ContentType"] = spec.content_type

    s3.upload_file(
        Filename=str(spec.path),
        Bucket=bucket,
        Key=spec.key,
        ExtraArgs=extra_args,
    )


def _delete_keys(s3, bucket: str, keys: list[str]) -> None:
    # S3 delete_objects supports up to 1000 keys per request
    for i in range(0, len(keys), 1000):
        chunk = keys[i : i + 1000]
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
        )


def _create_invalidation(cf, distribution_id: str, paths: list[str]) -> str:
    caller_ref = f"{int(time.time())}-{hashlib.sha1(','.join(paths).encode()).hexdigest()[:8]}"
    resp = cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "CallerReference": caller_ref,
            "Paths": {"Quantity": len(paths), "Items": paths},
        },
    )
    invalidation_id = resp["Invalidation"]["Id"]
    return invalidation_id


def _wait_invalidation(cf, distribution_id: str, invalidation_id: str, timeout_seconds: int = 900) -> None:
    deadline = time.time() + timeout_seconds
    last_status = None

    while True:
        if time.time() > deadline:
            raise TimeoutError(f"Timed out waiting for CloudFront invalidation {invalidation_id}")

        resp = cf.get_invalidation(DistributionId=distribution_id, Id=invalidation_id)
        status = resp["Invalidation"]["Status"]  # InProgress | Completed

        if status != last_status:
            print(f"[cloudfront] invalidation status => {status}", flush=True)
            last_status = status

        if status == "Completed":
            return

        time.sleep(10)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--distribution-id", required=True)
    p.add_argument("--build-dir", required=True)
    p.add_argument("--invalidate-paths", default="/*", help='Comma-separated paths, e.g. "/*,/index.html"')
    p.add_argument("--wait-invalidation", action="store_true")
    args = p.parse_args()

    build_dir = Path(args.build_dir).resolve()
    if not build_dir.exists() or not build_dir.is_dir():
        print(f"[deploy] ❌ build dir not found: {build_dir}", file=sys.stderr)
        return 1

    s3 = boto3.client("s3", region_name=args.region)
    cf = boto3.client("cloudfront", region_name=args.region)  # CloudFront is global, region is fine

    # Collect local specs
    specs = list(_iter_local_files(build_dir))
    local_keys = {s.key for s in specs}

    print(f"[deploy] build dir: {build_dir}", flush=True)
    print(f"[deploy] uploading {len(specs)} files to s3://{args.bucket}", flush=True)

    # Upload all
    for idx, spec in enumerate(specs, start=1):
        if idx % 50 == 0:
            print(f"[deploy] uploaded {idx}/{len(specs)}...", flush=True)
        _upload_file(s3, args.bucket, spec)

    # Delete stale keys
    print("[deploy] syncing deletions (S3 keys not present in build output)...", flush=True)
    existing_keys = _list_s3_keys(s3, args.bucket)
    to_delete = sorted(existing_keys - local_keys)

    if to_delete:
        print(f"[deploy] deleting {len(to_delete)} stale objects", flush=True)
        _delete_keys(s3, args.bucket, to_delete)
    else:
        print("[deploy] no stale objects to delete", flush=True)

    # Invalidate
    paths = [p.strip() for p in args.invalidate_paths.split(",") if p.strip()]
    print(f"[deploy] creating CloudFront invalidation for: {paths}", flush=True)
    invalidation_id = _create_invalidation(cf, args.distribution_id, paths)
    print(f"[cloudfront] invalidation id => {invalidation_id}", flush=True)

    if args.wait_invalidation:
        print("[cloudfront] waiting for invalidation to complete...", flush=True)
        _wait_invalidation(cf, args.distribution_id, invalidation_id)
        print("[cloudfront] ✅ invalidation completed", flush=True)

    print("[deploy] ✅ frontend deploy complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())