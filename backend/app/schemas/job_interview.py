from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class JobInterviewCreate(BaseModel):
    scheduled_at: datetime
    stage: Optional[str] = Field(default=None, max_length=50)
    kind: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)
    interviewer: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default="scheduled", max_length=20)
    notes: Optional[str] = None


class JobInterviewUpdate(BaseModel):
    scheduled_at: Optional[datetime] = None
    stage: Optional[str] = Field(default=None, max_length=50)
    kind: Optional[str] = Field(default=None, max_length=50)
    location: Optional[str] = Field(default=None, max_length=255)
    interviewer: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, max_length=20)
    notes: Optional[str] = None


class JobInterviewOut(BaseModel):
    id: int
    application_id: int
    scheduled_at: datetime
    stage: Optional[str] = None
    kind: Optional[str] = None
    location: Optional[str] = None
    interviewer: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


