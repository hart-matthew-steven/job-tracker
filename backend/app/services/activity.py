from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.job_activity import JobActivity


def log_job_activity(
    db: Session,
    *,
    job_id: int,
    user_id: int,
    type: str,
    message: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> JobActivity:
    ev = JobActivity(
        application_id=job_id,
        user_id=user_id,
        type=type,
        message=message,
        data=data,
    )
    db.add(ev)
    # Let caller decide commit timing; flush so `id`/`created_at` can be used.
    db.flush()
    return ev


