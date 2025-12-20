from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import desc, or_

from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.job_application import JobApplication
from app.models.job_application_tag import JobApplicationTag
from app.models.user import User
from app.services.activity import log_job_activity
from app.services.jobs import get_job_for_user, normalize_tags, set_job_tags
from app.schemas.job_application_update import JobApplicationUpdate
from app.schemas.job_application import (
    JobApplicationCreate,
    JobApplicationOut,
    JobApplicationDetailOut
)

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


@router.post("/", response_model=JobApplicationOut)
def create_job(
    payload: JobApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump()
    tags = normalize_tags(data.pop("tags", None))

    job = JobApplication(**data)
    job.user_id = user.id  # ✅ ownership

    job.last_activity_at = (
        job.applied_date
        or job.created_at
        or datetime.now(timezone.utc)
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    if tags:
        set_job_tags(db, job, tags)
        db.commit()
        db.refresh(job)

    return job


@router.get("/", response_model=list[JobApplicationOut])
def list_jobs(
    q: str | None = None,
    tag_q: str | None = None,
    tag: list[str] | None = Query(default=None),
    status: list[str] | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    qry = db.query(JobApplication).filter(JobApplication.user_id == user.id)  # ✅ scope

    # Text search (company/title/location)
    if q:
        term = str(q).strip()
        if term:
            like = f"%{term}%"
            qry = qry.filter(
                or_(
                    JobApplication.company_name.ilike(like),
                    JobApplication.job_title.ilike(like),
                    JobApplication.location.ilike(like),
                )
            )

    # Status filter (any-of)
    if status:
        statuses = [str(s).strip().lower() for s in status if s and str(s).strip()]
        if statuses:
            qry = qry.filter(JobApplication.status.in_(statuses))

    # Tags filter (any-of exact matches)
    if tag:
        tags = [str(t).strip().lower() for t in tag if t and str(t).strip()]
        if tags:
            qry = qry.filter(
                JobApplication.id.in_(
                    db.query(JobApplicationTag.application_id)
                    .filter(JobApplicationTag.tag.in_(tags))
                    .distinct()
                )
            )

    # Tag substring search (matches any tag containing the query)
    if tag_q:
        t = str(tag_q).strip().lower()
        if t:
            like = f"%{t}%"
            qry = qry.filter(
                JobApplication.id.in_(
                    db.query(JobApplicationTag.application_id)
                    .filter(JobApplicationTag.tag.ilike(like))
                    .distinct()
                )
            )

    return qry.order_by(desc(JobApplication.last_activity_at), desc(JobApplication.created_at)).all()


@router.get("/{job_id}", response_model=JobApplicationDetailOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_job_for_user(db, job_id, user.id)


@router.patch("/{job_id}", response_model=JobApplicationOut)
def update_job(
    job_id: int,
    payload: JobApplicationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return job

    if "tags" in data:
        before = set(getattr(job, "tags", []) or [])
        tags = normalize_tags(data.get("tags"))
        after = set(tags)
        set_job_tags(db, job, tags)
        added = sorted(list(after - before))
        removed = sorted(list(before - after))
        if added or removed:
            log_job_activity(
                db,
                job_id=job.id,
                user_id=user.id,
                type="tags_updated",
                message="Tags updated",
                data={"added": added, "removed": removed},
            )
        data.pop("tags", None)

    # normalize status
    if "status" in data and data["status"] is not None:
        prev_status = str(job.status or "").strip().lower()
        next_status = str(data["status"]).strip().lower()
        data["status"] = next_status
        if next_status and next_status != prev_status:
            log_job_activity(
                db,
                job_id=job.id,
                user_id=user.id,
                type="status_changed",
                message=f"Status changed to {next_status}",
                data={"from": prev_status or None, "to": next_status},
            )

    # trim strings
    for k, v in list(data.items()):
        if isinstance(v, str):
            data[k] = v.strip()

    for k, v in data.items():
        setattr(job, k, v)

    job.last_activity_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(job)
    return job