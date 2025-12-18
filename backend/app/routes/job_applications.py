from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from sqlalchemy import desc

from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.job_application import JobApplication
from app.models.user import User
from app.schemas.job_application_update import JobApplicationUpdate
from app.schemas.job_application import (
    JobApplicationCreate,
    JobApplicationOut,
    JobApplicationDetailOut
)

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


def _get_job_for_user(db: Session, job_id: int, user_id: int) -> JobApplication:
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")
    return job


@router.post("/", response_model=JobApplicationOut)
def create_job(
    payload: JobApplicationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    data = payload.model_dump()

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
    return job


@router.get("/", response_model=list[JobApplicationOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(JobApplication)
        .filter(JobApplication.user_id == user.id)  # ✅ scope
        .order_by(desc(JobApplication.last_activity_at), desc(JobApplication.created_at))
        .all()
    )


@router.get("/{job_id}", response_model=JobApplicationDetailOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _get_job_for_user(db, job_id, user.id)


@router.patch("/{job_id}", response_model=JobApplicationOut)
def update_job(
    job_id: int,
    payload: JobApplicationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return job

    # normalize status
    if "status" in data and data["status"] is not None:
        data["status"] = data["status"].strip().lower()

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