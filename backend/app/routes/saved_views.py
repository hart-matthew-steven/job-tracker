from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.models.saved_view import SavedView
from app.schemas.saved_view import SavedViewCreate, SavedViewOut, SavedViewUpdate
from app.schemas.auth import MessageOut


router = APIRouter(prefix="/saved-views", tags=["saved-views"], dependencies=[Depends(get_current_user)])


def _get_view_for_user(db: Session, view_id: int, user_id: int) -> SavedView:
    v = db.query(SavedView).filter(SavedView.id == view_id, SavedView.user_id == user_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return v


@router.get("/", response_model=list[SavedViewOut])
def list_saved_views(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(SavedView)
        .filter(SavedView.user_id == user.id)
        .order_by(desc(SavedView.updated_at), desc(SavedView.created_at))
        .all()
    )


@router.post("/", response_model=SavedViewOut, status_code=status.HTTP_201_CREATED)
def create_saved_view(
    payload: SavedViewCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    # Enforce unique name per user (simple UX).
    exists = db.query(SavedView.id).filter(SavedView.user_id == user.id, SavedView.name == name).first()
    if exists:
        raise HTTPException(status_code=409, detail="A saved view with that name already exists")

    v = SavedView(user_id=user.id, name=name, data=payload.data)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.patch("/{view_id}", response_model=SavedViewOut)
def update_saved_view(
    view_id: int,
    payload: SavedViewUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = _get_view_for_user(db, view_id, user.id)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return v

    if "name" in data and data["name"] is not None:
        name = str(data["name"]).strip()
        if not name:
            raise HTTPException(status_code=400, detail="Name is required")
        # uniqueness check
        exists = (
            db.query(SavedView.id)
            .filter(SavedView.user_id == user.id, SavedView.name == name, SavedView.id != v.id)
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="A saved view with that name already exists")
        v.name = name

    if "data" in data and data["data"] is not None:
        v.data = data["data"]

    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/{view_id}", response_model=MessageOut)
def delete_saved_view(
    view_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    v = _get_view_for_user(db, view_id, user.id)
    db.delete(v)
    db.commit()
    return {"message": "Saved view deleted"}


