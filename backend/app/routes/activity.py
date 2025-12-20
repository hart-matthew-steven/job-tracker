from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.job_activity import JobActivity
from app.models.user import User
from app.schemas.job_activity import JobActivityOut
from app.services.jobs import get_job_for_user


router = APIRouter(prefix="/jobs", tags=["activity"], dependencies=[Depends(get_current_user)])


@router.get("/{job_id}/activity", response_model=list[JobActivityOut])
def list_activity(
    job_id: int,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_job_for_user(db, job_id, user.id)

    limit2 = max(1, min(int(limit or 50), 200))
    return (
        db.query(JobActivity)
        .filter(JobActivity.application_id == job_id, JobActivity.user_id == user.id)
        .order_by(desc(JobActivity.created_at), desc(JobActivity.id))
        .limit(limit2)
        .all()
    )


