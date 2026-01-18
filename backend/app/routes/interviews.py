from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.job_application import JobApplication
from app.models.job_interview import JobInterview
from app.models.user import User
from app.schemas.job_interview import JobInterviewCreate, JobInterviewOut, JobInterviewUpdate
from app.schemas.auth import MessageOut
from app.services.activity import log_job_activity
from app.services.jobs import get_job_for_user


router = APIRouter(prefix="/jobs", tags=["interviews"], dependencies=[Depends(get_current_user)])


def _get_interview_for_user(db: Session, job_id: int, interview_id: int, user_id: int) -> JobInterview:
    iv = (
        db.query(JobInterview)
        .filter(
            JobInterview.id == interview_id,
            JobInterview.application_id == job_id,
            JobInterview.user_id == user_id,
        )
        .first()
    )
    if not iv:
        raise HTTPException(status_code=404, detail="Interview not found")
    return iv


@router.get("/{job_id}/interviews", response_model=list[JobInterviewOut])
def list_interviews(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_job_for_user(db, job_id, user.id)
    return (
        db.query(JobInterview)
        .filter(JobInterview.application_id == job_id, JobInterview.user_id == user.id)
        .order_by(desc(JobInterview.scheduled_at), desc(JobInterview.id))
        .all()
    )


@router.post("/{job_id}/interviews", response_model=JobInterviewOut)
def create_interview(
    job_id: int,
    payload: JobInterviewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

    iv = JobInterview(
        application_id=job.id,
        user_id=user.id,
        scheduled_at=payload.scheduled_at,
        stage=(payload.stage or "").strip().lower() or None,
        kind=(payload.kind or "").strip().lower() or None,
        location=(payload.location or "").strip() or None,
        interviewer=(payload.interviewer or "").strip() or None,
        status=(payload.status or "scheduled").strip().lower() or "scheduled",
        notes=payload.notes,
    )
    db.add(iv)
    db.flush()

    job.last_activity_at = datetime.now(timezone.utc)

    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="interview_added",
        message="Interview added",
        data={"interview_id": iv.id, "scheduled_at": iv.scheduled_at.isoformat()},
    )

    db.commit()
    db.refresh(iv)
    return iv


@router.patch("/{job_id}/interviews/{interview_id}", response_model=JobInterviewOut)
def update_interview(
    job_id: int,
    interview_id: int,
    payload: JobInterviewUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)
    iv = _get_interview_for_user(db, job_id, interview_id, user.id)

    prev = {
        "scheduled_at": iv.scheduled_at.isoformat() if iv.scheduled_at else None,
        "stage": iv.stage,
        "kind": iv.kind,
        "location": iv.location,
        "interviewer": iv.interviewer,
        "status": iv.status,
        "notes": iv.notes,
    }

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return iv

    if "stage" in data and data["stage"] is not None:
        data["stage"] = str(data["stage"]).strip().lower() or None
    if "kind" in data and data["kind"] is not None:
        data["kind"] = str(data["kind"]).strip().lower() or None
    if "location" in data and data["location"] is not None:
        data["location"] = str(data["location"]).strip() or None
    if "interviewer" in data and data["interviewer"] is not None:
        data["interviewer"] = str(data["interviewer"]).strip() or None
    if "status" in data and data["status"] is not None:
        data["status"] = str(data["status"]).strip().lower() or "scheduled"

    for k, v in data.items():
        setattr(iv, k, v)

    job.last_activity_at = datetime.now(timezone.utc)

    changes = {}
    for key in prev.keys():
        if key not in data:
            continue
        next_value = getattr(iv, key)
        if isinstance(next_value, datetime):
            next_value = next_value.isoformat()
        if prev[key] != next_value:
            changes[key] = {"from": prev[key], "to": next_value}

    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="interview_updated",
        message="Interview updated",
        data={
            "changes": changes,
            "scheduled_at": iv.scheduled_at.isoformat() if iv.scheduled_at else None,
            "stage": iv.stage,
            "kind": iv.kind,
            "interviewer": iv.interviewer,
            "location": iv.location,
            "status": iv.status,
        },
    )

    db.commit()
    db.refresh(iv)
    return iv


@router.delete("/{job_id}/interviews/{interview_id}", response_model=MessageOut)
def delete_interview(
    job_id: int,
    interview_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)
    iv = _get_interview_for_user(db, job_id, interview_id, user.id)

    db.delete(iv)
    db.flush()

    job.last_activity_at = datetime.now(timezone.utc)

    log_job_activity(
        db,
        job_id=job.id,
        user_id=user.id,
        type="interview_deleted",
        message="Interview deleted",
        data={"interview_id": interview_id},
    )

    db.commit()
    return {"message": "Interview deleted"}


