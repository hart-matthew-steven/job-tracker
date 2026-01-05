from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.job_activity import JobActivity
from app.models.user import User
from app.schemas.job_activity import JobActivityOut, JobActivityPageOut
from app.services.jobs import get_job_for_user


router = APIRouter(prefix="/jobs", tags=["activity"], dependencies=[Depends(get_current_user)])


@router.get("/{job_id}/activity", response_model=JobActivityPageOut)
def list_activity(
    job_id: int,
    limit: int = Query(default=20, ge=1, le=200),
    cursor_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_job_for_user(db, job_id, user.id)

    limit2 = max(1, min(int(limit or 20), 200))
    query = (
        db.query(JobActivity)
        .filter(JobActivity.application_id == job_id, JobActivity.user_id == user.id)
        .order_by(desc(JobActivity.created_at), desc(JobActivity.id))
    )
    if cursor_id:
        query = query.filter(JobActivity.id < cursor_id)

    items = query.limit(limit2).all()
    next_cursor = items[-1].id if len(items) == limit2 else None
    return JobActivityPageOut(items=items, next_cursor=next_cursor)


