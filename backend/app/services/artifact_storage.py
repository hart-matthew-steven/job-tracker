from __future__ import annotations

import re
import tempfile
import uuid

import boto3

from app.core.config import settings


_s3 = boto3.client("s3", region_name=settings.AWS_REGION)
_SANITIZE_RE = re.compile(r"[^A-Za-z0-9_.-]")


def _bucket() -> str:
    return settings.AI_ARTIFACTS_BUCKET


def build_s3_key(user_id: int, artifact_id: int, filename: str) -> str:
    safe = _SANITIZE_RE.sub("_", filename or "artifact")
    prefix = settings.AI_ARTIFACTS_S3_PREFIX.rstrip("/")
    return f"{prefix}/users/{user_id}/artifacts/{artifact_id}/{uuid.uuid4()}_{safe}"


def presign_upload(key: str, content_type: str | None) -> str:
    params: dict[str, str] = {"Bucket": _bucket(), "Key": key}
    if content_type:
        params["ContentType"] = content_type
    return _s3.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=600,
    )


def presign_view(key: str) -> str:
    return _s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": _bucket(), "Key": key},
        ExpiresIn=600,
    )


def download_to_tempfile(key: str) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    _s3.download_file(_bucket(), key, tmp.name)
    return tmp.name


def delete(key: str) -> None:
    _s3.delete_object(Bucket=_bucket(), Key=key)
