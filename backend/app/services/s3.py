import uuid
from dataclasses import dataclass

import boto3

from app.core.config import settings


@dataclass(frozen=True)
class PresignUploadResult:
    s3_key: str
    upload_url: str


def _client():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def build_s3_key(job_id: int, doc_type: str, original_filename: str) -> str:
    safe_name = original_filename.replace("/", "_").replace("\\", "_")
    return f"{settings.S3_PREFIX}/jobs/{job_id}/{doc_type}/{uuid.uuid4()}_{safe_name}"


def head_object(s3_key: str) -> dict:
    s3 = _client()
    return s3.head_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)


def presign_upload(job_id: int, doc_type: str, filename: str, content_type: str | None) -> PresignUploadResult:
    s3 = _client()
    key = build_s3_key(job_id, doc_type, filename)

    params = {"Bucket": settings.S3_BUCKET_NAME, "Key": key}
    if content_type:
        params["ContentType"] = content_type

    url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params=params,
        ExpiresIn=60 * 10,  # 10 minutes
    )

    return PresignUploadResult(s3_key=key, upload_url=url)


def presign_download(s3_key: str) -> str:
    s3 = _client()
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=60 * 10,
    )
    return url


def delete_object(s3_key: str) -> None:
    s3 = _client()
    s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)