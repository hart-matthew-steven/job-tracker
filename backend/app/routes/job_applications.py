from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload
from datetime import datetime, timezone, timedelta
from sqlalchemy import desc, or_, func

from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.job_application import JobApplication
from app.models.job_application_tag import JobApplicationTag
from app.models.job_application_note import JobApplicationNote
from app.models.job_interview import JobInterview
from app.models.job_activity import JobActivity
from app.models.user import User
from app.services.activity import log_job_activity
from app.services.jobs import get_job_for_user, normalize_tags, set_job_tags
from app.schemas.job_application_update import JobApplicationUpdate
from app.schemas.job_application import (
    JobApplicationCreate,
    JobApplicationOut,
    JobApplicationDetailOut,
    JobDetailsBundleOut,
    JobBoardCardOut,
    JobsBoardOut,
)
from app.schemas.job_activity import JobActivityPageOut

BOARD_STATUS_ORDER = [
    "applied",
    "recruiter_screen",
    "interviewing",
    "onsite",
    "offer",
    "accepted",
    "rejected",
    "withdrawn",
    "archived",
]

router = APIRouter(prefix="/jobs", tags=["jobs"], dependencies=[Depends(get_current_user)])


def _with_timezone(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


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


@router.get("/board", response_model=JobsBoardOut)
def get_board_view(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    jobs = (
        db.query(JobApplication)
        .filter(JobApplication.user_id == user.id)
        .options(selectinload(JobApplication.tag_rows))
        .order_by(desc(JobApplication.updated_at))
        .all()
    )

    now = datetime.now(timezone.utc)
    cards: list[JobBoardCardOut] = []
    counts: dict[str, int] = {}

    for job in jobs:
        status = (job.status or "applied").strip().lower()
        counts[status] = counts.get(status, 0) + 1

        needs_follow_up = False
        reference = job.next_action_at or job.last_action_at or job.last_activity_at or job.updated_at
        ref_dt = _with_timezone(reference)
        next_dt = _with_timezone(job.next_action_at)
        if next_dt:
            needs_follow_up = next_dt <= now
        elif ref_dt:
            needs_follow_up = (now - ref_dt) >= timedelta(days=5)

        cards.append(
            JobBoardCardOut(
                id=job.id,
                status=status,
                company_name=job.company_name,
                job_title=job.job_title,
                location=job.location,
                updated_at=job.updated_at,
                last_activity_at=job.last_activity_at,
                last_action_at=job.last_action_at,
                next_action_at=job.next_action_at,
                next_action_title=job.next_action_title,
                priority=job.priority or "normal",
                tags=job.tags,
                needs_follow_up=needs_follow_up,
            )
        )

    dynamic_statuses = [status for status in counts.keys() if status not in BOARD_STATUS_ORDER]
    ordered_statuses = BOARD_STATUS_ORDER + sorted(dynamic_statuses)

    return JobsBoardOut(
        statuses=ordered_statuses,
        jobs=cards,
        meta={
            "counts": counts,
            "total": len(cards),
        },
    )


@router.get("/search", response_model=JobsBoardOut)
def search_jobs(
    q: str = Query(min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    term = q.strip()
    if not term:
        return JobsBoardOut(statuses=[], jobs=[], meta={"counts": {}, "total": 0})

    like = f"%{term}%"
    jobs = (
        db.query(JobApplication)
        .outerjoin(JobApplicationNote, JobApplicationNote.application_id == JobApplication.id)
        .filter(
            JobApplication.user_id == user.id,
            or_(
                JobApplication.company_name.ilike(like),
                JobApplication.job_title.ilike(like),
                JobApplication.location.ilike(like),
                JobApplicationNote.body.ilike(like),
            ),
        )
        .options(selectinload(JobApplication.tag_rows))
        .order_by(desc(JobApplication.updated_at))
        .limit(limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    cards: list[JobBoardCardOut] = []
    statuses = set()
    for job in jobs:
        status = (job.status or "applied").strip().lower()
        statuses.add(status)
        reference = job.next_action_at or job.last_action_at or job.last_activity_at or job.updated_at
        needs_follow_up = False
        next_dt = _with_timezone(job.next_action_at)
        ref_dt = _with_timezone(reference)
        if next_dt:
            needs_follow_up = next_dt <= now
        elif ref_dt:
            needs_follow_up = (now - ref_dt) >= timedelta(days=5)

        cards.append(
            JobBoardCardOut(
                id=job.id,
                status=status,
                company_name=job.company_name,
                job_title=job.job_title,
                location=job.location,
                updated_at=job.updated_at,
                last_activity_at=job.last_activity_at,
                last_action_at=job.last_action_at,
                next_action_at=job.next_action_at,
                next_action_title=job.next_action_title,
                priority=job.priority or "normal",
                tags=job.tags,
                needs_follow_up=needs_follow_up,
            )
        )

    ordered_statuses = [s for s in BOARD_STATUS_ORDER if s in statuses] + sorted(statuses - set(BOARD_STATUS_ORDER))
    return JobsBoardOut(statuses=ordered_statuses, jobs=cards, meta={"query": term, "total": len(cards)})


@router.get("/{job_id}", response_model=JobApplicationDetailOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_job_for_user(db, job_id, user.id)


@router.get("/{job_id}/details", response_model=JobDetailsBundleOut)
def get_job_details(
    job_id: int,
    activity_limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = get_job_for_user(db, job_id, user.id)

    notes = (
        db.query(JobApplicationNote)
        .filter(JobApplicationNote.application_id == job.id)
        .order_by(JobApplicationNote.created_at.desc(), JobApplicationNote.id.desc())
        .all()
    )

    interviews = (
        db.query(JobInterview)
        .filter(JobInterview.application_id == job.id, JobInterview.user_id == user.id)
        .order_by(desc(JobInterview.scheduled_at), desc(JobInterview.id))
        .all()
    )

    activity_items = (
        db.query(JobActivity)
        .filter(JobActivity.application_id == job.id, JobActivity.user_id == user.id)
        .order_by(desc(JobActivity.created_at), desc(JobActivity.id))
        .limit(activity_limit)
        .all()
    )
    activity_next = activity_items[-1].id if len(activity_items) == activity_limit else None

    return JobDetailsBundleOut(
        job=job,
        notes=notes,
        interviews=interviews,
        activity=JobActivityPageOut(items=activity_items, next_cursor=activity_next),
    )


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