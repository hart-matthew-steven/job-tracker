from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.models.job_application import JobApplication
from app.models.job_document import JobDocument
from app.models.user import User
from app.schemas.job_document import (
    DocumentPresignIn,
    DocumentOut,
    PresignDownloadOut,
    PresignUploadOut,
    DocumentConfirmIn
)
from app.schemas.job_document_scan import DocumentScanIn
from app.services.s3 import delete_object, presign_download, presign_upload, head_object

SINGLE_DOC_TYPES = {"resume", "job_description", "cover_letter"}
MULTI_DOC_TYPES = {"thank_you"}
ALLOWED_DOC_TYPES = SINGLE_DOC_TYPES | MULTI_DOC_TYPES

router = APIRouter(prefix="/jobs", tags=["documents"], dependencies=[Depends(get_current_user)])


def _maybe_limit(rule: str):
    if not settings.ENABLE_RATE_LIMITING:
        def passthrough(fn):
            return fn
        return passthrough
    return limiter.limit(rule)


def _get_job_for_user(db: Session, job_id: int, user_id: int) -> JobApplication:
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")
    return job


@router.post("/{job_id}/documents/presign-upload", response_model=PresignUploadOut)
@_maybe_limit("10/minute")
def create_document_presign_upload(
    request: Request,
    job_id: int,
    payload: DocumentPresignIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    doc_type = (payload.doc_type or "").strip().lower()
    if doc_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid doc_type: {doc_type}")

    filename = (payload.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="filename is required")

    if payload.size_bytes is None:
        raise HTTPException(status_code=400, detail="size_bytes is required")

    if payload.size_bytes > settings.MAX_UPLOAD_BYTES:
        max_mb = settings.MAX_UPLOAD_BYTES / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size is {max_mb:.1f} MB.",
        )

    pending_count = (
        db.query(JobDocument)
        .filter(
            JobDocument.application_id == job.id,
            JobDocument.status == "pending",
        )
        .count()
    )
    if pending_count >= settings.MAX_PENDING_UPLOADS_PER_JOB:
        raise HTTPException(
            status_code=429,
            detail="Too many pending uploads. Please finish or delete existing uploads first.",
        )

    # If single-type, delete the existing doc (DB + S3)
    if doc_type in SINGLE_DOC_TYPES:
        existing = (
            db.query(JobDocument)
            .filter(
                JobDocument.application_id == job.id,
                JobDocument.doc_type == doc_type,
            )
            .order_by(JobDocument.created_at.desc())
            .first()
        )
        if existing:
            try:
                delete_object(existing.s3_key)
            except Exception:
                pass
            db.delete(existing)
            db.commit()

    result = presign_upload(
        job_id=job.id,
        doc_type=doc_type,
        filename=filename,
        content_type=payload.content_type,
    )

    doc = JobDocument(
        application_id=job.id,
        doc_type=doc_type,
        s3_key=result.s3_key,
        original_filename=filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        status="pending",
        uploaded_at=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return {"document": doc, "upload_url": result.upload_url}


@router.get("/{job_id}/documents", response_model=list[DocumentOut])
def list_documents(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    return (
        db.query(JobDocument)
        .filter(JobDocument.application_id == job.id)
        .order_by(JobDocument.created_at.desc())
        .all()
    )


@router.get("/{job_id}/documents/{doc_id}/presign-download", response_model=PresignDownloadOut)
def get_document_download_url(
    job_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == doc_id, JobDocument.application_id == job.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Recommended: block downloads until scan passed
    if getattr(doc, "status", None) and doc.status != "uploaded":
        raise HTTPException(status_code=409, detail="Document is not ready to download yet")

    return {"download_url": presign_download(doc.s3_key)}


@router.delete("/{job_id}/documents/{doc_id}")
@_maybe_limit("30/minute")
def delete_document(
    request: Request,
    job_id: int,
    doc_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == doc_id, JobDocument.application_id == job.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        delete_object(doc.s3_key)
    except Exception:
        pass

    db.delete(doc)

    job.last_activity_at = datetime.now(timezone.utc)

    db.commit()
    return {"deleted": True}


@router.post("/{job_id}/documents/confirm-upload", response_model=DocumentOut)
@_maybe_limit("20/minute")
def confirm_upload(
    request: Request,
    job_id: int,
    payload: DocumentConfirmIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == payload.document_id, JobDocument.application_id == job.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Must exist in S3
    try:
        meta = head_object(doc.s3_key)
    except Exception:
        raise HTTPException(
            status_code=409,
            detail="Upload not found in S3 yet. Try again in a moment.",
        )

    s3_size = int(meta.get("ContentLength", 0))
    if s3_size <= 0:
        raise HTTPException(status_code=409, detail="Upload is empty or not ready yet.")

    if s3_size > settings.MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max allowed size is {settings.MAX_UPLOAD_BYTES / (1024*1024):.1f} MB.",
        )

    # Mark confirmed -> scanning (virus scan decides final)
    doc.status = "scanning"
    doc.size_bytes = s3_size
    doc.uploaded_at = datetime.now(timezone.utc)

    job.last_activity_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(doc)
    return doc


@router.post("/{job_id}/documents/scan-result")
def document_scan_result(
    request: Request,
    job_id: int,
    payload: DocumentScanIn,
    x_scan_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    # Lambda endpoint: shared secret auth
    if not settings.DOC_SCAN_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="Server missing DOC_SCAN_SHARED_SECRET")

    if x_scan_secret != settings.DOC_SCAN_SHARED_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Load job + doc (no user here; secret is the auth)
    job = db.query(JobApplication).filter(JobApplication.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == payload.document_id, JobDocument.application_id == job_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if payload.result == "clean":
        doc.status = "uploaded"
        doc.uploaded_at = doc.uploaded_at or datetime.now(timezone.utc)
        job.last_activity_at = datetime.now(timezone.utc)

    elif payload.result == "infected":
        doc.status = "infected"
        try:
            delete_object(doc.s3_key)
        except Exception:
            pass

    else:
        doc.status = "failed"

    db.commit()
    return {"ok": True, "document_id": doc.id, "status": doc.status}