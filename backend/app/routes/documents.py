from datetime import datetime, timezone
import hashlib
import logging
import uuid
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
    ConfirmUploadIn
)
from app.schemas.job_document_scan import DocumentScanIn
from app.services.s3 import delete_object, presign_download, presign_upload, head_object
from app.services.activity import log_job_activity
from app.services.jobs import get_job_for_user
from app.services.documents import (
    enforce_max_upload_bytes,
    enforce_pending_upload_limit,
    maybe_replace_single_doc,
    normalize_doc_type,
    require_filename,
    require_size_bytes,
)

router = APIRouter(prefix="/jobs", tags=["documents"])
logger = logging.getLogger(__name__)


def _maybe_limit(rule: str):
    if not settings.ENABLE_RATE_LIMITING:
        def passthrough(fn):
            return fn
        return passthrough
    return limiter.limit(rule)


@router.post("/{job_id}/documents/presign-upload", response_model=PresignUploadOut)
@_maybe_limit("10/minute")
def create_document_presign_upload(
    request: Request,
    job_id: int,
    payload: DocumentPresignIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

    doc_type = normalize_doc_type(payload.doc_type)
    filename = require_filename(payload.filename)
    size_bytes = require_size_bytes(payload.size_bytes)
    enforce_max_upload_bytes(size_bytes)
    enforce_pending_upload_limit(db, job.id)
    maybe_replace_single_doc(db, job.id, doc_type)

    # Create DB row first so we can embed document_id into the S3 key for downstream scanning.
    doc = JobDocument(
        application_id=job.id,
        doc_type=doc_type,
        # Temporary placeholder, replaced below before commit.
        s3_key=f"__pending__/{uuid.uuid4()}",
        original_filename=filename,
        content_type=payload.content_type,
        size_bytes=size_bytes,
        status="pending",
        uploaded_at=None,
        scan_status="PENDING",
        scan_checked_at=None,
        scan_message=None,
        quarantined_s3_key=None,
    )
    db.add(doc)
    db.flush()  # assign doc.id without committing

    result = presign_upload(
        job_id=job.id,
        doc_type=doc_type,
        filename=filename,
        content_type=payload.content_type,
        document_id=doc.id,
    )
    doc.s3_key = result.s3_key

    db.commit()
    db.refresh(doc)

    # Track that a document was created (pending upload)
    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="document_added",
        message="Document added",
        data={"document_id": doc.id, "doc_type": doc_type, "filename": filename},
    )
    db.commit()

    return {"document": doc, "upload_url": result.upload_url}


@router.get("/{job_id}/documents", response_model=list[DocumentOut])
def list_documents(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

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
    job = get_job_for_user(db, job_id, user.id)

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == doc_id, JobDocument.application_id == job.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Block downloads until malware scan is clean.
    scan_status = getattr(doc, "scan_status", None)
    if scan_status and str(scan_status).upper() != "CLEAN":
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
    job = get_job_for_user(db, job_id, user.id)

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

    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="document_deleted",
        message="Document deleted",
        data={"document_id": doc_id, "doc_type": getattr(doc, "doc_type", None), "filename": getattr(doc, "original_filename", None)},
    )

    db.commit()
    return {"deleted": True}


@router.post("/{job_id}/documents/confirm-upload", response_model=DocumentOut)
@_maybe_limit("20/minute")
def confirm_upload(
    request: Request,
    job_id: int,
    payload: ConfirmUploadIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == payload.document_id, JobDocument.application_id == job.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Idempotency / guardrails: only allow confirm while pending.
    # If already confirmed/scanning/uploaded/etc, don't re-confirm.
    if getattr(doc, "status", None) and doc.status != "pending":
        raise HTTPException(status_code=409, detail="Upload already confirmed")

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
    doc.scan_status = "PENDING"
    doc.size_bytes = s3_size
    doc.uploaded_at = datetime.now(timezone.utc)

    job.last_activity_at = datetime.now(timezone.utc)

    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="document_uploaded",
        message="Document uploaded",
        data={"document_id": doc.id, "doc_type": getattr(doc, "doc_type", None), "filename": getattr(doc, "original_filename", None)},
    )

    db.commit()
    db.refresh(doc)
    return doc


def _secret_signature(value: str | None) -> str:
    if not value:
        return "none"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]


@router.post("/{job_id}/documents/{document_id}/scan-result")
def document_scan_result(
    request: Request,
    job_id: int,
    document_id: int,
    payload: DocumentScanIn,
    x_scan_secret: str | None = Header(default=None, alias="x-scan-secret"),
    x_doc_scan_secret: str | None = Header(default=None, alias="x-doc-scan-secret"),
    db: Session = Depends(get_db),
):
    # Lambda endpoint: shared secret auth
    if not settings.GUARD_DUTY_ENABLED:
        logger.info("GuardDuty disabled; ignoring /jobs/%s/documents/%s/scan-result", job_id, document_id)
        return {"ok": False, "guard_duty_enabled": False}

    if not settings.DOC_SCAN_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="Server missing DOC_SCAN_SHARED_SECRET")

    provided_secret = x_scan_secret or x_doc_scan_secret
    if provided_secret:
        logger.info(
            "GuardDuty secret debug: header_used=%s provided_len=%s configured_len=%s provided_sig=%s expected_sig=%s",
            "X-Scan-Secret" if x_scan_secret else "X-Doc-Scan-Secret",
            len(provided_secret),
            len(settings.DOC_SCAN_SHARED_SECRET),
            _secret_signature(provided_secret),
            _secret_signature(settings.DOC_SCAN_SHARED_SECRET),
        )
    if provided_secret != settings.DOC_SCAN_SHARED_SECRET:
        logger.info(
            "GuardDuty scan secret mismatch: header_present=%s provided_len=%s expected_len=%s",
            bool(provided_secret),
            len(provided_secret or ""),
            len(settings.DOC_SCAN_SHARED_SECRET or ""),
        )
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Load job + doc (no user here; secret is the auth)
    job = db.query(JobApplication).filter(JobApplication.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")

    payload_document_id = getattr(payload, "document_id", None)
    if payload_document_id and payload_document_id != document_id:
        logger.warning(
            "GuardDuty payload document_id mismatch: path=%s payload=%s",
            document_id,
            payload_document_id,
        )

    doc = (
        db.query(JobDocument)
        .filter(JobDocument.id == document_id, JobDocument.application_id == job_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    now = datetime.now(timezone.utc)

    # Idempotency: once CLEAN/INFECTED, keep it stable (safe for retries).
    existing = str(getattr(doc, "scan_status", "PENDING") or "PENDING").upper()
    if existing in {"CLEAN", "INFECTED"}:
        # Allow a "fill-in" for quarantined key if the first attempt quarantined but the callback retried.
        if existing == "INFECTED" and getattr(payload, "quarantined_s3_key", None) and not getattr(doc, "quarantined_s3_key", None):
            doc.quarantined_s3_key = payload.quarantined_s3_key
            db.commit()
        return {"ok": True, "document_id": doc.id, "scan_status": existing, "status": doc.status}

    if payload.result == "clean":
        doc.scan_status = "CLEAN"
        doc.scan_checked_at = now
        doc.scan_message = payload.detail
        doc.status = "uploaded"
        doc.uploaded_at = doc.uploaded_at or now
        job.last_activity_at = now

    elif payload.result == "infected":
        doc.scan_status = "INFECTED"
        doc.scan_checked_at = now
        doc.scan_message = payload.detail
        if getattr(payload, "quarantined_s3_key", None):
            doc.quarantined_s3_key = payload.quarantined_s3_key
        doc.status = "infected"

    else:
        doc.scan_status = "ERROR"
        doc.scan_checked_at = now
        doc.scan_message = payload.detail
        doc.status = "failed"

    db.commit()
    return {"ok": True, "document_id": doc.id, "scan_status": doc.scan_status, "status": doc.status}