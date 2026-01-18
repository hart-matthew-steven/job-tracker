from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ArtifactType(str, Enum):
    resume = "resume"
    job_description = "job_description"
    note = "note"


class ArtifactSourceType(str, Enum):
    upload = "upload"
    url = "url"
    paste = "paste"


class ArtifactStatus(str, Enum):
    pending = "pending"
    ready = "ready"
    failed = "failed"


class ArtifactUploadRequest(BaseModel):
    conversation_id: int
    artifact_type: ArtifactType
    filename: str
    content_type: str | None = None


class ArtifactUploadResponse(BaseModel):
    artifact_id: int
    upload_url: str


class ArtifactFinalizeResponse(BaseModel):
    artifact_id: int
    status: ArtifactStatus


class ArtifactTextRequest(BaseModel):
    conversation_id: int
    artifact_type: ArtifactType = Field(..., description="resume, job_description, or note")
    content: str = Field(..., min_length=1, max_length=200000)


class ArtifactUrlRequest(BaseModel):
    conversation_id: int
    artifact_type: ArtifactType
    url: HttpUrl


class ArtifactPinRequest(BaseModel):
    conversation_id: int


class ArtifactVersion(BaseModel):
    artifact_id: int
    artifact_type: ArtifactType
    version_number: int
    status: ArtifactStatus
    source_type: ArtifactSourceType
    created_at: str
    failure_reason: str | None = None
    view_url: str | None = None


class ConversationArtifactsResponse(BaseModel):
    artifacts: list[ArtifactVersion]
