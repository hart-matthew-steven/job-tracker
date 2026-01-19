from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

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


class ConversationArtifactSummary(BaseModel):
    role: ArtifactType
    artifact_id: int
    artifact_type: ArtifactType
    version_number: int
    status: ArtifactStatus
    source_type: ArtifactSourceType
    created_at: datetime
    pinned_at: datetime
    failure_reason: str | None = None
    view_url: str | None = None


class ConversationArtifactsResponse(BaseModel):
    artifacts: list[ConversationArtifactSummary]


class ArtifactHistoryEntry(BaseModel):
    artifact_id: int
    role: ArtifactType
    version_number: int
    status: ArtifactStatus
    source_type: ArtifactSourceType
    created_at: datetime
    pinned_at: datetime | None = None
    failure_reason: str | None = None


class ArtifactHistoryResponse(BaseModel):
    artifacts: list[ArtifactHistoryEntry]


class ArtifactDiffLine(BaseModel):
    op: Literal["equal", "insert", "delete", "replace"]
    text: str


class ArtifactDiffResponse(BaseModel):
    artifact_id: int
    compare_to_id: int
    artifact_version: int
    compare_version: int
    diff: list[ArtifactDiffLine]
