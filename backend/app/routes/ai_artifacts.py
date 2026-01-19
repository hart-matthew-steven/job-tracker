from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai_artifact import (
    ArtifactDiffResponse,
    ArtifactDiffLine,
    ArtifactFinalizeResponse,
    ArtifactHistoryEntry,
    ArtifactHistoryResponse,
    ArtifactPinRequest,
    ArtifactTextRequest,
    ArtifactStatus,
    ArtifactType,
    ArtifactUploadRequest,
    ArtifactUploadResponse,
    ArtifactUrlRequest,
    ConversationArtifactSummary,
    ConversationArtifactsResponse,
)
from app.services import artifact_storage
from app.services.artifacts import ArtifactNotFoundError, ArtifactService


router = APIRouter(prefix="/ai/artifacts", tags=["ai"])


def _service(db: Session, user: User) -> ArtifactService:
    return ArtifactService(db, user)


@router.post("/upload-url", response_model=ArtifactUploadResponse, status_code=status.HTTP_201_CREATED)
def create_upload_url(
    payload: ArtifactUploadRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactUploadResponse:
    service = _service(db, user)
    try:
        artifact, url = service.issue_upload(
            conversation_id=payload.conversation_id,
            artifact_type=payload.artifact_type,
            filename=payload.filename,
            content_type=payload.content_type,
        )
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    return ArtifactUploadResponse(artifact_id=artifact.id, upload_url=url)


@router.post("/{artifact_id}/complete-upload", response_model=ArtifactFinalizeResponse)
def finalize_upload(
    artifact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactFinalizeResponse:
    service = _service(db, user)
    try:
        artifact = service.mark_upload_complete(artifact_id)
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found") from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ArtifactFinalizeResponse(artifact_id=artifact.id, status=artifact.status.value)


@router.post("/text", response_model=ArtifactFinalizeResponse, status_code=status.HTTP_201_CREATED)
def create_text_artifact(
    payload: ArtifactTextRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactFinalizeResponse:
    service = _service(db, user)
    try:
        artifact = service.create_from_text(
            conversation_id=payload.conversation_id,
            artifact_type=payload.artifact_type,
            content=payload.content,
        )
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    return ArtifactFinalizeResponse(artifact_id=artifact.id, status=artifact.status.value)


@router.post("/url", response_model=ArtifactFinalizeResponse, status_code=status.HTTP_201_CREATED)
def create_url_artifact(
    payload: ArtifactUrlRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactFinalizeResponse:
    service = _service(db, user)
    try:
        artifact = service.create_from_url(
            conversation_id=payload.conversation_id,
            artifact_type=payload.artifact_type,
            url=str(payload.url),
        )
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    return ArtifactFinalizeResponse(artifact_id=artifact.id, status=artifact.status.value)


@router.post("/{artifact_id}/pin", response_model=ArtifactFinalizeResponse)
def pin_artifact(
    artifact_id: int,
    payload: ArtifactPinRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactFinalizeResponse:
    service = _service(db, user)
    try:
        artifact = service.pin_artifact(payload.conversation_id, artifact_id)
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found") from None
    return ArtifactFinalizeResponse(artifact_id=artifact.id, status=artifact.status.value)


@router.get("/conversations/{conversation_id}", response_model=ConversationArtifactsResponse)
def list_conversation_artifacts(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ConversationArtifactsResponse:
    service = _service(db, user)
    try:
        links = service.list_conversation_artifacts(conversation_id)
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None

    artifacts: list[ConversationArtifactSummary] = []
    for link in links:
        artifact = link.artifact
        if not artifact:
            continue
        view_url = None
        if artifact.s3_key and artifact.status == ArtifactStatus.ready and settings.AI_ARTIFACTS_BUCKET:
            view_url = artifact_storage.presign_view(artifact.s3_key)
        artifacts.append(
            ConversationArtifactSummary(
                role=link.role,
                artifact_id=artifact.id,
                artifact_type=artifact.artifact_type,
                version_number=artifact.version_number,
                status=artifact.status,
                source_type=artifact.source_type,
                created_at=artifact.created_at,
                pinned_at=link.pinned_at,
                failure_reason=artifact.failure_reason,
                view_url=view_url,
            )
        )
    return ConversationArtifactsResponse(artifacts=artifacts)


@router.get("/conversations/{conversation_id}/history", response_model=ArtifactHistoryResponse)
def get_artifact_history(
    conversation_id: int,
    role: ArtifactType,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactHistoryResponse:
    service = _service(db, user)
    try:
        versions = service.list_role_history(conversation_id, role)
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    entries = [
        ArtifactHistoryEntry(
            artifact_id=artifact.id,
            role=artifact.artifact_type,
            version_number=artifact.version_number,
            status=artifact.status,
            source_type=artifact.source_type,
            created_at=artifact.created_at,
            pinned_at=None,
            failure_reason=artifact.failure_reason,
        )
        for artifact in versions
    ]
    return ArtifactHistoryResponse(artifacts=entries)


@router.get("/{artifact_id}/diff", response_model=ArtifactDiffResponse)
def get_artifact_diff(
    artifact_id: int,
    compare_to_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ArtifactDiffResponse:
    service = _service(db, user)
    try:
        base, other, diff = service.get_artifact_diff(artifact_id, compare_to_id)
    except ArtifactNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found") from None
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ArtifactDiffResponse(
        artifact_id=base.id,
        compare_to_id=other.id,
        artifact_version=base.version_number,
        compare_version=other.version_number,
        diff=[ArtifactDiffLine(op=op, text=text) for op, text in diff],
    )
