from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.job_application import JobApplication
from app.models.job_application_note import JobApplicationNote
from app.models.user import User
from app.schemas.job_application_note import NoteCreate, NoteOut

router = APIRouter(prefix="/jobs", tags=["notes"], dependencies=[Depends(get_current_user)])


def _get_job_for_user(db: Session, job_id: int, user_id: int) -> JobApplication:
    job = (
        db.query(JobApplication)
        .filter(JobApplication.id == job_id, JobApplication.user_id == user_id)
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="Job application not found")
    return job


@router.post("/{job_id}/notes", response_model=NoteOut)
def add_note(
    job_id: int,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = _get_job_for_user(db, job_id, user.id)

    note = JobApplicationNote(application_id=job.id, body=payload.body)
    db.add(note)
    db.flush()  # so note.created_at is available if server-defaulted

    job.last_activity_at = note.created_at or datetime.now(timezone.utc)

    db.commit()
    db.refresh(note)
    return note


@router.get("/{job_id}/notes", response_model=list[NoteOut])
def list_notes(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_job_for_user(db, job_id, user.id)

    return (
        db.query(JobApplicationNote)
        .filter(JobApplicationNote.application_id == job_id)
        .order_by(JobApplicationNote.created_at.desc())
        .all()
    )


@router.delete("/{job_id}/notes/{note_id}")
def delete_note(
    job_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _get_job_for_user(db, job_id, user.id)

    note = (
        db.query(JobApplicationNote)
        .filter(
            JobApplicationNote.id == note_id,
            JobApplicationNote.application_id == job_id,
        )
        .first()
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    db.delete(note)
    db.flush()

    # If you want to be “correct”: set last_activity_at to latest remaining note,
    # otherwise bump to now (simple + consistent)
    job = db.query(JobApplication).filter(JobApplication.id == job_id).first()
    if job:
        job.last_activity_at = datetime.now(timezone.utc)

    db.commit()
    return {"deleted": True}