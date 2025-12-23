from __future__ import annotations

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.job_document import JobDocument


router = APIRouter(prefix="/internal/documents", tags=["internal"], include_in_schema=False)

logger = logging.getLogger(__name__)


def _require_internal_token(
    x_internal_token: str | None,
    x_scan_secret: str | None,
    x_doc_scan_secret: str | None,
) -> None:
    """
    Shared-secret auth for Lambda → backend callbacks.

    Accept both headers for backwards compatibility:
    - x-internal-token (preferred for new internal endpoints)
    - x-scan-secret (legacy endpoint header)
    - x-doc-scan-secret (preferred for GuardDuty forwarder)
    """
    if not settings.GUARD_DUTY_ENABLED:
        return

    if not settings.DOC_SCAN_SHARED_SECRET:
        raise HTTPException(status_code=500, detail="Server missing DOC_SCAN_SHARED_SECRET")

    token = x_doc_scan_secret or x_internal_token or x_scan_secret
    if token != settings.DOC_SCAN_SHARED_SECRET:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def _normalize_result(raw: str | None) -> str:
    r = (raw or "").strip().lower()
    if r in {"clean", "infected", "error"}:
        return r
    if r in {"ok"}:
        return "clean"
    if r in {"pending"}:
        return "error"
    raise HTTPException(status_code=400, detail=f"Invalid result: {raw}")


def _normalize_scan_status(raw: str | None) -> str:
    """
    Normalize GuardDuty-forwarded scan_status into internal result strings.
    Expected inputs: CLEAN | INFECTED | ERROR (case-insensitive).
    """
    r = (raw or "").strip().upper()
    if r in {"CLEAN", "INFECTED", "ERROR"}:
        return r.lower()
    raise HTTPException(status_code=400, detail=f"Invalid scan_status: {raw}")


def _clip_scan_message(msg: str | None, *, max_len: int = 1024) -> str | None:
    """
    Defensive truncation: DB column is VARCHAR(1024). Lambda/tooling can emit very verbose errors.
    """
    if not isinstance(msg, str):
        return None
    s = msg.strip()
    if not s:
        return None
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


@router.get("/{document_id}")
def get_internal_document_state(
    document_id: int,
    x_internal_token: str | None = Header(default=None, alias="x-internal-token"),
    x_scan_secret: str | None = Header(default=None, alias="x-scan-secret"),
    x_doc_scan_secret: str | None = Header(default=None, alias="x-doc-scan-secret"),
    db: Session = Depends(get_db),
):
    _require_internal_token(x_internal_token, x_scan_secret, x_doc_scan_secret)
    if not settings.GUARD_DUTY_ENABLED:
        logger.info("GuardDuty disabled; internal document state requested but feature is off document_id=%s", document_id)
        raise HTTPException(status_code=404, detail="GuardDuty integration disabled")

    doc = db.query(JobDocument).filter(JobDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return {
        "document_id": doc.id,
        "application_id": doc.application_id,
        "s3_key": doc.s3_key,
        "status": getattr(doc, "status", None),
        "scan_status": getattr(doc, "scan_status", None),
        "quarantined_s3_key": getattr(doc, "quarantined_s3_key", None),
    }


@router.post("/{document_id}/scan-result")
def post_internal_document_scan_result(
    document_id: int,
    payload: dict,
    x_internal_token: str | None = Header(default=None, alias="x-internal-token"),
    x_scan_secret: str | None = Header(default=None, alias="x-scan-secret"),
    x_doc_scan_secret: str | None = Header(default=None, alias="x-doc-scan-secret"),
    db: Session = Depends(get_db),
):
    """
    Internal callback endpoint for the malware scanning Lambda.

    Payload shape (minimal):
      {
        "scan_status": "CLEAN" | "INFECTED" | "ERROR" (preferred; GuardDuty forwarder),
        "result": "CLEAN" | "INFECTED" | "ERROR" (legacy; case-insensitive; also accepts clean/infected/error),
        "scan_message": "...",                     (optional)
      }
    """
    if not settings.GUARD_DUTY_ENABLED:
        logger.info("GuardDuty disabled; ignoring internal scan result for document_id=%s", document_id)
        return {"ok": False, "guard_duty_enabled": False}

    _require_internal_token(x_internal_token, x_scan_secret, x_doc_scan_secret)

    doc = db.query(JobDocument).filter(JobDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    scan_status_raw = payload.get("scan_status") if isinstance(payload, dict) else None
    if isinstance(scan_status_raw, str) and scan_status_raw.strip():
        result = _normalize_scan_status(scan_status_raw)
    else:
        # Legacy callers
        result_raw = payload.get("result") if isinstance(payload, dict) else None
        result = _normalize_result(result_raw if isinstance(result_raw, str) else None)
    scan_message = payload.get("scan_message") if isinstance(payload, dict) else None
    # Keep quarantined_s3_key for backwards compatibility, but GuardDuty flow does not quarantine.
    quarantined = payload.get("quarantined_s3_key") if isinstance(payload, dict) else None

    now = datetime.now(timezone.utc)

    existing = str(getattr(doc, "scan_status", "PENDING") or "PENDING").upper()
    if existing in {"CLEAN", "INFECTED"}:
        # Idempotency: safe for SQS redeliveries / retries.
        # Allow a "fill-in" for quarantined key if the first attempt quarantined but the callback retried.
        if existing == "INFECTED" and isinstance(quarantined, str) and quarantined and not getattr(doc, "quarantined_s3_key", None):
            doc.quarantined_s3_key = quarantined
            db.commit()
        return {"ok": True, "document_id": doc.id, "scan_status": existing, "status": doc.status}

    if result == "clean":
        doc.scan_status = "CLEAN"
        doc.status = "uploaded"
        doc.uploaded_at = doc.uploaded_at or now
        doc.scan_checked_at = now
        doc.scan_message = _clip_scan_message(scan_message if isinstance(scan_message, str) else None)
        doc.quarantined_s3_key = None
    elif result == "infected":
        doc.scan_status = "INFECTED"
        doc.status = "infected"
        doc.scan_checked_at = now
        doc.scan_message = _clip_scan_message(scan_message if isinstance(scan_message, str) else None)
        doc.quarantined_s3_key = quarantined if isinstance(quarantined, str) and quarantined else doc.quarantined_s3_key
    else:
        doc.scan_status = "ERROR"
        doc.status = "failed"
        doc.scan_checked_at = now
        doc.scan_message = _clip_scan_message(scan_message if isinstance(scan_message, str) else None)

    db.commit()
    return {"ok": True, "document_id": doc.id, "scan_status": doc.scan_status, "status": doc.status}


