#!/usr/bin/env python3
"""
Deploy static frontend assets to S3 + invalidate CloudFront with release + rollback.

New design:
- Upload build output to: s3://<bucket>/releases/<release-id>/...
- Promote that release to bucket root (copy objects) so CloudFront keeps serving /index.html
- Maintain pointer: s3://<bucket>/_releases/current.json
- Optional CloudFront invalidation wait
- Optional health check on FRONTEND_URL (expects HTTP 200 for / and /index.html)
- Roll back by re-promoting previous release if deploy/health fails

Usage:
  python scripts/deploy_frontend.py \
    --region us-east-2 \
    --bucket my-bucket-name \
    --distribution-id ABCDEFGHIJKLMN \
    --build-dir frontend-web/dist \
    --release-id 20251230015322-ca3ffcf \
    --frontend-url https://mywebsite.com \
    --invalidate-paths "/*" \
    --wait-invalidation
"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import boto3


HTML_CACHE_CONTROL = "no-cache, no-store, must-revalidate"
ASSET_CACHE_CONTROL = "public, max-age=31536000, immutable"

RELEASES_PREFIX = "releases/"
META_PREFIX = "_releases/"
CURRENT_POINTER_KEY = f"{META_PREFIX}current.json"


@dataclass(frozen=True)
class UploadSpec:
    key: str          # relative key (no prefix)
    path: Path
    content_type: str | None
    cache_control: str


def _iter_local_files(build_dir: Path) -> Iterable[UploadSpec]:
    for p in build_dir.rglob("*"):
        if p.is_dir():
            continue
        rel = p.relative_to(build_dir).as_posix().lstrip("./")
        content_type, _ = mimetypes.guess_type(str(p))

        if rel.endswith(".html"):
            cache_control = HTML_CACHE_CONTROL
        else:
            cache_control = ASSET_CACHE_CONTROL

        yield UploadSpec(
            key=rel,
            path=p,
            content_type=content_type,
            cache_control=cache_control,
        )


def _s3_list_keys(s3, bucket: str, prefix: str = "") -> set[str]:
    keys: set[str] = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            k = obj.get("Key")
            if k:
                keys.add(k)
    return keys


def _s3_put_json(s3, bucket: str, key: str, payload: dict) -> None:
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(payload, indent=2).encode("utf-8"),
        ContentType="application/json",
        CacheControl="no-cache, no-store, must-revalidate",
    )


def _s3_get_json(s3, bucket: str, key: str) -> Optional[dict]:
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read().decode("utf-8")
        return json.loads(body)
    except s3.exceptions.NoSuchKey:
        return None
    except Exception:
        # if it exists but malformed or access issue, bubble up
        raise


def _upload_file(s3, bucket: str, full_key: str, spec: UploadSpec) -> None:
    extra_args = {"CacheControl": spec.cache_control}
    if spec.content_type:
        extra_args["ContentType"] = spec.content_type

    s3.upload_file(
        Filename=str(spec.path),
        Bucket=bucket,
        Key=full_key,
        ExtraArgs=extra_args,
    )


def _delete_keys(s3, bucket: str, keys: list[str]) -> None:
    for i in range(0, len(keys), 1000):
        chunk = keys[i : i + 1000]
        s3.delete_objects(
            Bucket=bucket,
            Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True},
        )


def _copy_object(s3, bucket: str, src_key: str, dest_key: str, cache_control: str, content_type: str | None) -> None:
    copy_source = {"Bucket": bucket, "Key": src_key}

    extra = {
        "Bucket": bucket,
        "Key": dest_key,
        "CopySource": copy_source,
        # IMPORTANT: force metadata replacement so Cache-Control on root objects is correct
        "MetadataDirective": "REPLACE",
        "CacheControl": cache_control,
    }
    if content_type:
        extra["ContentType"] = content_type

    s3.copy_object(**extra)


def _create_invalidation(cf, distribution_id: str, paths: list[str]) -> str:
    caller_ref = f"{int(time.time())}-{hashlib.sha1(','.join(paths).encode()).hexdigest()[:8]}"
    resp = cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "CallerReference": caller_ref,
            "Paths": {"Quantity": len(paths), "Items": paths},
        },
    )
    return resp["Invalidation"]["Id"]


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


def _http_get_status(url: str, timeout_seconds: int = 10) -> int:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0


def _health_check(frontend_url: str, attempts: int = 18, sleep_seconds: int = 5) -> None:
    """
    Check that the site is serving content.
    We try both "/" and "/index.html" to avoid edge cases.
    """
    base = frontend_url.rstrip("/")
    targets = [f"{base}/", f"{base}/index.html"]

    for i in range(1, attempts + 1):
        codes = [(_t, _http_get_status(_t)) for _t in targets]
        msg = ", ".join([f"{t} => {c}" for t, c in codes])
        print(f"[health] attempt {i}/{attempts} => {msg}", flush=True)

        if any(c == 200 for _, c in codes):
            return

        time.sleep(sleep_seconds)

    raise RuntimeError(f"Frontend health check failed (expected HTTP 200) for {targets}")


def _spec_cache_control(rel_key: str) -> str:
    return HTML_CACHE_CONTROL if rel_key.endswith(".html") else ASSET_CACHE_CONTROL


def _promote_release_to_root(s3, bucket: str, release_prefix: str, local_specs: list[UploadSpec]) -> None:
    """
    Copy from releases/<release-id>/... to root keys.
    Also delete stale root keys that are not in this release output.
    Never deletes anything under releases/ or _releases/.
    """
    # Copy each built artifact to root (dest key = spec.key)
    print(f"[promote] promoting {len(local_specs)} objects to bucket root...", flush=True)
    for idx, spec in enumerate(local_specs, start=1):
        src_key = f"{release_prefix}{spec.key}"
        dest_key = spec.key
        cache_control = _spec_cache_control(spec.key)
        _copy_object(s3, bucket, src_key, dest_key, cache_control, spec.content_type)

        if idx % 50 == 0:
            print(f"[promote] copied {idx}/{len(local_specs)}...", flush=True)

    # Compute stale root keys
    desired_root = {spec.key for spec in local_specs}

    # List ALL keys, then filter to "root-ish" keys only
    all_keys = _s3_list_keys(s3, bucket, prefix="")
    root_keys = {
        k for k in all_keys
        if not (k.startswith(RELEASES_PREFIX) or k.startswith(META_PREFIX))
    }

    to_delete = sorted(root_keys - desired_root)
    if to_delete:
        print(f"[promote] deleting {len(to_delete)} stale root objects", flush=True)
        _delete_keys(s3, bucket, to_delete)
    else:
        print("[promote] no stale root objects to delete", flush=True)


def _read_current_release_id(s3, bucket: str) -> Optional[str]:
    data = _s3_get_json(s3, bucket, CURRENT_POINTER_KEY)
    if not data:
        return None
    rid = data.get("current_release_id")
    if isinstance(rid, str) and rid.strip():
        return rid.strip()
    return None


def _write_current_release(s3, bucket: str, new_release_id: str, previous_release_id: Optional[str]) -> None:
    payload = {
        "current_release_id": new_release_id,
        "previous_release_id": previous_release_id or "",
        "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    _s3_put_json(s3, bucket, CURRENT_POINTER_KEY, payload)


def _rollback_to_previous(s3, bucket: str, prev_release_id: str, local_specs: list[UploadSpec]) -> None:
    """
    Rollback by re-promoting previous release to root.
    NOTE: We use current local_specs just to know which *root* keys to manage.
    That’s sufficient because root should match the build layout.
    """
    prev_prefix = f"{RELEASES_PREFIX}{prev_release_id}/"
    print(f"[rollback] promoting previous release back to root: {prev_release_id}", flush=True)

    # For rollback, we must copy objects that exist in the previous release.
    # We’ll discover the keys in that release prefix and map them to root.
    prev_keys = _s3_list_keys(s3, bucket, prefix=prev_prefix)
    rel_keys = sorted([k[len(prev_prefix):] for k in prev_keys if k.endswith("/") is False])

    # Build lookup of content-types from local build (best effort)
    ct_map = {spec.key: spec.content_type for spec in local_specs}

    print(f"[rollback] copying {len(rel_keys)} objects to root...", flush=True)
    for idx, rel_key in enumerate(rel_keys, start=1):
        src_key = f"{prev_prefix}{rel_key}"
        dest_key = rel_key
        cache_control = _spec_cache_control(rel_key)
        _copy_object(s3, bucket, src_key, dest_key, cache_control, ct_map.get(rel_key))

        if idx % 50 == 0:
            print(f"[rollback] copied {idx}/{len(rel_keys)}...", flush=True)

    # Delete stale root keys that are not in prev release
    desired_root = set(rel_keys)
    all_keys = _s3_list_keys(s3, bucket, prefix="")
    root_keys = {
        k for k in all_keys
        if not (k.startswith(RELEASES_PREFIX) or k.startswith(META_PREFIX))
    }
    to_delete = sorted(root_keys - desired_root)
    if to_delete:
        print(f"[rollback] deleting {len(to_delete)} stale root objects", flush=True)
        _delete_keys(s3, bucket, to_delete)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--region", required=True)
    p.add_argument("--bucket", required=True)
    p.add_argument("--distribution-id", required=True)
    p.add_argument("--build-dir", required=True)
    p.add_argument("--release-id", required=True)
    p.add_argument("--frontend-url", required=False, default="")
    p.add_argument("--invalidate-paths", default="/*", help='Comma-separated paths, e.g. "/*,/index.html"')
    p.add_argument("--wait-invalidation", action="store_true")
    p.add_argument("--timeout-seconds", type=int, default=900)
    args = p.parse_args()

    build_dir = Path(args.build_dir).resolve()
    if not build_dir.exists() or not build_dir.is_dir():
        print(f"[deploy] ❌ build dir not found: {build_dir}", file=sys.stderr, flush=True)
        return 1

    release_id = args.release_id.strip()
    if not release_id:
        print("[deploy] ❌ release-id is empty", file=sys.stderr, flush=True)
        return 1

    release_prefix = f"{RELEASES_PREFIX}{release_id}/"

    s3 = boto3.client("s3", region_name=args.region)
    cf = boto3.client("cloudfront", region_name=args.region)

    specs = list(_iter_local_files(build_dir))
    if not specs:
        print(f"[deploy] ❌ no files found under build dir: {build_dir}", file=sys.stderr, flush=True)
        return 1

    # Determine previous release (for rollback)
    prev_release_id = _read_current_release_id(s3, args.bucket)
    print(f"[deploy] build dir       : {build_dir}", flush=True)
    print(f"[deploy] release id      : {release_id}", flush=True)
    print(f"[deploy] previous release: {prev_release_id or '(none)'}", flush=True)
    print(f"[deploy] upload prefix   : s3://{args.bucket}/{release_prefix}", flush=True)

    try:
        # 1) Upload to releases/<release-id>/ (do NOT delete other releases)
        print(f"[deploy] uploading {len(specs)} files to release prefix...", flush=True)
        for idx, spec in enumerate(specs, start=1):
            full_key = f"{release_prefix}{spec.key}"
            _upload_file(s3, args.bucket, full_key, spec)
            if idx % 50 == 0:
                print(f"[deploy] uploaded {idx}/{len(specs)}...", flush=True)

        # 2) Promote release to root (copy + delete stale root keys)
        _promote_release_to_root(s3, args.bucket, release_prefix, specs)

        # 3) Update pointer AFTER promotion succeeds
        _write_current_release(s3, args.bucket, release_id, prev_release_id)

        # 4) CloudFront invalidation
        paths = [p.strip() for p in args.invalidate_paths.split(",") if p.strip()]
        print(f"[deploy] creating CloudFront invalidation for: {paths}", flush=True)
        invalidation_id = _create_invalidation(cf, args.distribution_id, paths)
        print(f"[cloudfront] invalidation id => {invalidation_id}", flush=True)

        if args.wait_invalidation:
            print("[cloudfront] waiting for invalidation to complete...", flush=True)
            _wait_invalidation(cf, args.distribution_id, invalidation_id, timeout_seconds=args.timeout_seconds)
            print("[cloudfront] ✅ invalidation completed", flush=True)

        # 5) Health check (optional, but strongly recommended)
        if args.frontend_url.strip():
            print(f"[deploy] running frontend health check: {args.frontend_url}", flush=True)
            _health_check(args.frontend_url.strip())
            print("[deploy] ✅ frontend health check passed", flush=True)
        else:
            print("[deploy] (skipping health check; --frontend-url not provided)", flush=True)

        print("[deploy] ✅ frontend deploy complete", flush=True)
        return 0

    except Exception as e:
        print(f"[deploy] ❌ deploy failed: {e}", file=sys.stderr, flush=True)

        # Roll back if we know a previous release
        if prev_release_id:
            try:
                _rollback_to_previous(s3, args.bucket, prev_release_id, specs)

                # Reset pointer back
                _write_current_release(s3, args.bucket, prev_release_id, "")

                # Invalidate again to flush edge caches
                paths = [p.strip() for p in args.invalidate_paths.split(",") if p.strip()]
                print(f"[rollback] creating CloudFront invalidation for: {paths}", flush=True)
                invalidation_id = _create_invalidation(cf, args.distribution_id, paths)
                print(f"[cloudfront] invalidation id => {invalidation_id}", flush=True)

                if args.wait_invalidation:
                    print("[cloudfront] waiting for invalidation to complete...", flush=True)
                    _wait_invalidation(cf, args.distribution_id, invalidation_id, timeout_seconds=args.timeout_seconds)
                    print("[cloudfront] ✅ invalidation completed", flush=True)

                if args.frontend_url.strip():
                    print(f"[rollback] running frontend health check: {args.frontend_url}", flush=True)
                    _health_check(args.frontend_url.strip())
                    print("[rollback] ✅ frontend health check passed", flush=True)

                print("[rollback] ✅ rollback completed", flush=True)

            except Exception as re:
                print(f"[rollback] ❌ rollback failed: {re}", file=sys.stderr, flush=True)

        return 1


if __name__ == "__main__":
    raise SystemExit(main())