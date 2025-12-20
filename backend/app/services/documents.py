from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.job_document import JobDocument
from app.services.s3 import delete_object

SINGLE_DOC_TYPES = {"resume", "job_description", "cover_letter"}
MULTI_DOC_TYPES = {"thank_you"}
ALLOWED_DOC_TYPES = SINGLE_DOC_TYPES | MULTI_DOC_TYPES


def normalize_doc_type(raw: str | None) -> str:
    doc_type = (raw or "").strip().lower()
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")
    return doc_type


def require_filename(raw: str | None) -> str:
    filename = (raw or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")
    return filename


def require_size_bytes(size_bytes: int | None) -> int:
    if size_bytes is None:
        raise HTTPException(status_code=400, detail="size_bytes is required")
    return int(size_bytes)


def enforce_max_upload_bytes(size_bytes: int) -> None:
    if size_bytes > settings.MAX_UPLOAD_BYTES:
        max_mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size is {max_mb:.1f} MB.",
        )


def enforce_pending_upload_limit(db: Session, job_id: int) -> None:
    pending_count = (
        db.query(JobDocument)
        .filter(
            JobDocument.application_id == job_id,
            JobDocument.status == "pending",
        )
        .count()
    )
    if pending_count >= settings.MAX_PENDING_UPLOADS_PER_JOB:
        raise HTTPException(
            status_code=429,
            detail="Too many pending uploads. Please finish or delete existing uploads first.",
        )


def maybe_replace_single_doc(db: Session, job_id: int, doc_type: str) -> None:
    """
    If doc_type is single-valued, delete the existing doc (DB + S3), if any.
    """
    if doc_type not in SINGLE_DOC_TYPES:
        return

    existing = (
        db.query(JobDocument)
        .filter(
            JobDocument.application_id == job_id,
            JobDocument.doc_type == doc_type,
        )
        .order_by(JobDocument.created_at.desc())
        .first()
    )
    if not existing:
        return

    try:
        delete_object(existing.s3_key)
    except Exception:
        pass
    db.delete(existing)
    db.commit()


