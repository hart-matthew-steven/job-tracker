from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
import hashlib
import base64

import boto3
from botocore.exceptions import ClientError
import requests


def _env(name: str) -> str:
    v = os.getenv(name)
    if v is None or not str(v).strip():
        raise RuntimeError(f"Missing env var: {name}")
    return str(v).strip()


@lru_cache(maxsize=1)
def _load_scan_secret() -> str:
    arn = _env("DOC_SCAN_SHARED_SECRET_ARN")
    client = boto3.client("secretsmanager")
    resp = client.get_secret_value(SecretId=arn)
    secret = resp.get("SecretString")
    if not secret:
        binary = resp.get("SecretBinary")
        if binary:
            if isinstance(binary, str):
                binary = binary.encode("utf-8")
            secret = base64.b64decode(binary).decode("utf-8")
    if not secret:
        raise RuntimeError("DOC_SCAN_SHARED_SECRET secret is empty")
    return secret.strip()


def _parse_document_id_from_key(key: str) -> int | None:
    """
    Expected key format:
      <prefix>/jobs/<job_id>/<doc_type>/<document_id>/<uuid>_<original_filename>
    We parse the segment after <doc_type>.
    """
    if not key:
        return None
    parts = [p for p in key.split("/") if p]
    try:
        jobs_idx = parts.index("jobs")
    except ValueError:
        return None
    # jobs/<job_id>/<doc_type>/<document_id>/...
    if len(parts) < jobs_idx + 4:
        return None
    doc_id_raw = parts[jobs_idx + 3]
    try:
        return int(doc_id_raw)
    except ValueError:
        return None


def _parse_job_id_from_key(key: str) -> int | None:
    if not key:
        return None
    parts = [p for p in key.split("/") if p]
    try:
        jobs_idx = parts.index("jobs")
    except ValueError:
        return None
    if len(parts) < jobs_idx + 2:
        return None
    job_id_raw = parts[jobs_idx + 1]
    try:
        return int(job_id_raw)
    except ValueError:
        return None


def _find_first(obj: Any, candidates: set[str]) -> Any | None:
    """
    Walk a nested dict/list and return the first value for a matching key name.
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k in candidates:
                return v
        for v in obj.values():
            found = _find_first(v, candidates)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, candidates)
            if found is not None:
                return found
    return None


def _extract_tag_value(obj: Any, *, tag_key: str) -> str | None:
    """
    Try to locate a specific tag value inside a nested EventBridge/CloudTrail-style payload.

    Supports common shapes:
    - {"tags": [{"key": "K", "value": "V"}, ...]}
    - {"tagSet": [{"key": "K", "value": "V"}, ...]}
    - {"tagging": {"tagSet": [...]}}
    - {"Tags": [{"Key": "K", "Value": "V"}, ...]}
    - {"tagging": "K=V&Other=X"} (URL-encoded tag string)
    """
    if isinstance(obj, dict):
        # Common AWS tag-list containers
        for container_key in ("tags", "tagSet", "Tags"):
            maybe = obj.get(container_key)
            v = _extract_tag_value(maybe, tag_key=tag_key)
            if v is not None:
                return v

        # CloudTrail-style nested container
        maybe_tagging = obj.get("tagging")
        v = _extract_tag_value(maybe_tagging, tag_key=tag_key)
        if v is not None:
            return v

        # Sometimes tags are encoded as a single string (e.g. CloudTrail requestParameters.tagging)
        if isinstance(maybe_tagging, str) and maybe_tagging:
            # Example: "Tagging=GuardDutyMalwareScanStatus=NO_THREATS_FOUND&..."
            # We'll do a simple split parse without importing urllib.
            for part in maybe_tagging.replace("Tagging=", "").split("&"):
                if "=" not in part:
                    continue
                k, v = part.split("=", 1)
                if k == tag_key and v:
                    return v

        # Recurse into values
        for v in obj.values():
            found = _extract_tag_value(v, tag_key=tag_key)
            if found is not None:
                return found

    elif isinstance(obj, list):
        # Tag list entries
        for item in obj:
            if isinstance(item, dict):
                # AWS sometimes uses Key/Value capitalization
                k = item.get("key") if isinstance(item.get("key"), str) else item.get("Key")
                v = item.get("value") if isinstance(item.get("value"), str) else item.get("Value")
                if k == tag_key and isinstance(v, str) and v.strip():
                    return v.strip()
            found = _extract_tag_value(item, tag_key=tag_key)
            if found is not None:
                return found

    return None


def _extract_bucket_and_key(event: dict[str, Any]) -> tuple[str | None, str | None]:
    """
    GuardDuty / EventBridge payload shapes can vary by feature/version.
    We attempt common fields first, then fall back to a recursive search.
    """
    detail = event.get("detail") if isinstance(event, dict) else None
    if isinstance(detail, dict):
        # Common GuardDuty S3 detail shapes
        bucket = (
            detail.get("bucketName")
            or detail.get("s3Bucket")
            or detail.get("bucket")
            or (detail.get("resource", {}) or {}).get("s3BucketName")
        )
        key = detail.get("objectKey") or detail.get("s3ObjectKey") or detail.get("key")

        if isinstance(bucket, str) and isinstance(key, str):
            return bucket, key

    # Fallback: recursive search for likely field names
    bucket_any = _find_first(event, {"bucketName", "s3BucketName", "bucket", "bucket_name"})
    key_any = _find_first(event, {"objectKey", "s3ObjectKey", "key", "object_key", "s3_key"})

    bucket = bucket_any if isinstance(bucket_any, str) else None
    key = key_any if isinstance(key_any, str) else None
    return bucket, key


def _extract_completion_state(detail: dict[str, Any]) -> str | None:
    """
    GuardDuty Malware Protection for S3 emits a scan completion state (e.g. COMPLETED).
    This is *not* a verdict; verdict is derived from the GuardDutyMalwareScanStatus tag.
    """
    for k in (
        "scanStatus",
        "scan_status",
        "completionState",
        "completion_state",
        "scanCompletionState",
        "scan_completion_state",
    ):
        v = detail.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    v_any = _find_first(
        detail,
        {"scanStatus", "scan_status", "completionState", "completion_state", "scanCompletionState", "scan_completion_state"},
    )
    return v_any.strip() if isinstance(v_any, str) and v_any.strip() else None


def _extract_guardduty_verdict(event: dict[str, Any]) -> str | None:
    """
    Verdict is derived from the S3 object tag:
      GuardDutyMalwareScanStatus = NO_THREATS_FOUND | THREATS_FOUND | FAILED | ACCESS_DENIED | UNSUPPORTED

    GuardDuty findings are not guaranteed for clean scans, so we do not rely on finding types.
    """
    return _extract_tag_value(event, tag_key="GuardDutyMalwareScanStatus")


_S3_CLIENT = None


def _s3() -> Any:
    global _S3_CLIENT
    if _S3_CLIENT is None:
        _S3_CLIENT = boto3.client("s3")
    return _S3_CLIENT


def _extract_guardduty_verdict_from_s3_tags(*, bucket: str, key: str) -> str | None:
    """
    Fallback when EventBridge doesn't include object tags:
    read S3 object tags and extract GuardDutyMalwareScanStatus.
    """
    try:
        res = _s3().get_object_tagging(Bucket=bucket, Key=key)
    except ClientError:
        # Any S3/IAM/NotFound error => we cannot determine verdict here.
        return None

    tagset = res.get("TagSet")
    if not isinstance(tagset, list):
        return None
    for t in tagset:
        if not isinstance(t, dict):
            continue
        k = t.get("Key")
        v = t.get("Value")
        if k == "GuardDutyMalwareScanStatus" and isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _map_verdict(raw: str | None) -> tuple[str, str]:
    """
    Map GuardDuty malware verdicts -> backend scan_status.
    """
    r = (raw or "").strip().upper()
    if r == "NO_THREATS_FOUND":
        return "CLEAN", r
    if r == "THREATS_FOUND":
        return "INFECTED", r
    if r in {"FAILED", "ACCESS_DENIED", "UNSUPPORTED"}:
        return "ERROR", r
    return "ERROR", r or "UNKNOWN"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:  # noqa: ARG001
    """
    EventBridge-triggered Lambda to forward GuardDuty Malware Protection for S3 scan results
    to the backend internal callback endpoint.

    Env vars (assumed to exist; managed outside repo):
    - BACKEND_BASE_URL
    - DOC_SCAN_SHARED_SECRET
    """
    backend_base = _env("BACKEND_BASE_URL").rstrip("/")
    secret = _load_scan_secret()

    detail = event.get("detail") if isinstance(event, dict) else None
    if not isinstance(detail, dict):
        # Log full event only if parsing fails
        print(json.dumps({"msg": "parse_failed", "reason": "missing_detail", "event": event}))
        raise RuntimeError("GuardDuty event missing detail")

    bucket, key = _extract_bucket_and_key(event)
    if not bucket or not key:
        print(json.dumps({"msg": "parse_failed", "reason": "missing_bucket_or_key", "event": event}))
        raise RuntimeError("Could not extract bucket/key from GuardDuty event")

    doc_id = _parse_document_id_from_key(key)
    if doc_id is None:
        print(json.dumps({"msg": "parse_failed", "reason": "missing_document_id_in_key", "bucket": bucket, "key": key, "event": event}))
        raise RuntimeError("Could not parse document_id from key")

    completion_raw = _extract_completion_state(detail)
    completion_norm = (completion_raw or "").strip().upper() or "UNKNOWN"

    verdict_raw = _extract_guardduty_verdict(event)
    if not verdict_raw or not verdict_raw.strip():
        print(json.dumps({"msg": "verdict_missing_in_event"}))
        verdict_raw = _extract_guardduty_verdict_from_s3_tags(bucket=bucket, key=key)
        if verdict_raw and verdict_raw.strip():
            print(json.dumps({"msg": "verdict_from_s3_tags", "verdict": verdict_raw.strip()}))

    scan_status, verdict_norm = _map_verdict(verdict_raw)

    # If verdict still cannot be determined, log available detail keys only.
    if verdict_norm == "UNKNOWN":
        print(json.dumps({"msg": "verdict_unknown", "detail_keys": sorted([k for k in detail.keys() if isinstance(k, str)])}))

    # Scan message for UI/debugging (keep short; backend truncates defensively anyway)
    if completion_norm == "COMPLETED":
        scan_message = f"Scan completed: {verdict_norm} (GuardDuty)"
    else:
        scan_message = f"Scan {completion_norm.lower()}: {verdict_norm} (GuardDuty)"

    # New scan-result callback lives under /jobs/{job_id}/documents/{document_id}/scan-result
    # Since the S3 key includes the job_id as part of the prefix, extract it alongside doc_id.
    job_id = _parse_job_id_from_key(key)
    if job_id is None:
        print(json.dumps({"msg": "parse_failed", "reason": "missing_job_id_in_key", "bucket": bucket, "key": key, "event": event}))
        raise RuntimeError("Could not parse job_id from key")

    url = f"{backend_base}/jobs/{job_id}/documents/{doc_id}/scan-result"
    payload: dict[str, Any] = {
        "document_id": doc_id,
        "result": scan_status.lower(),
        "detail": scan_message,
        "bucket": bucket,
        "s3_key": key,
        "provider": "guardduty",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }

    headers = {"X-Scan-Secret": secret, "Content-Type": "application/json"}

    res = requests.post(url, headers=headers, json=payload, timeout=15)
    if res.status_code < 200 or res.status_code >= 300:
        body = (res.text or "").strip()
        raise RuntimeError(f"Backend callback failed: status={res.status_code} body={body}")

    print(json.dumps({"msg": "forward_ok", "document_id": doc_id, "scan_status": scan_status, "bucket": bucket, "key": key}))
    return {"ok": True, "document_id": doc_id, "scan_status": scan_status}


