from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.job_application import JobApplication
from app.models.job_application_tag import JobApplicationTag


def get_job_for_user(db: Session, job_id: int, user_id: int) -> JobApplication:
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")
    return job


def normalize_tags(raw) -> list[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        return []
    cleaned: list[str] = []
    for t in raw:
        if t is None:
            continue
        s = str(t).strip().lower()
        if not s:
            continue
        if len(s) > 64:
            s = s[:64]
        cleaned.append(s)
    # de-dupe while preserving order
    seen = set()
    out: list[str] = []
    for t in cleaned:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out[:50]


def set_job_tags(db: Session, job: JobApplication, tags: list[str]) -> None:
    """
    Replace semantics: delete missing, add new.
    """
    desired = set(tags)
    existing_rows = list(getattr(job, "tag_rows", []) or [])
    existing = set([r.tag for r in existing_rows if r and r.tag])

    to_delete = existing - desired
    to_add = desired - existing

    if to_delete:
        for r in existing_rows:
            if r.tag in to_delete:
                db.delete(r)

    for t in to_add:
        db.add(JobApplicationTag(application_id=job.id, tag=t))


