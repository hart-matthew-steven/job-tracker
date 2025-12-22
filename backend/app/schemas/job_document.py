from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Allowed document types
DocType = Literal[
    "resume",
    "job_description",
    "cover_letter",
    "thank_you",
]


# ---------- INPUT SCHEMAS ----------

class DocumentPresignIn(BaseModel):
    doc_type: DocType
    filename: str = Field(min_length=1, max_length=512)
    content_type: str | None = None
    size_bytes: int = Field(
        gt=0,
        description="File size in bytes (validated server-side)",
    )


class DocumentConfirmIn(BaseModel):
    s3_key: str = Field(min_length=1)


# ---------- OUTPUT SCHEMAS ----------

class DocumentOut(BaseModel):
    id: int
    application_id: int

    doc_type: DocType
    original_filename: str
    content_type: str | None
    size_bytes: int | None

    # Upload lifecycle (existing UI expectations): pending | scanning | uploaded | infected | failed
    status: str
    # Malware scan result (new, more explicit): PENDING | CLEAN | INFECTED | ERROR
    scan_status: str
    scan_checked_at: datetime | None = None
    scan_message: str | None = None
    quarantined_s3_key: str | None = None
    uploaded_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PresignUploadOut(BaseModel):
    document: DocumentOut
    upload_url: str


class PresignDownloadOut(BaseModel):
    download_url: str


class ConfirmUploadIn(BaseModel):
    document_id: int
    size_bytes: int | None = None