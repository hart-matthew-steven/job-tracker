from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo

from app.schemas.job_application_note import NoteOut
from app.schemas.job_activity import JobActivityPageOut
from app.schemas.job_interview import JobInterviewOut

ET = ZoneInfo("America/New_York")

class JobApplicationCreate(BaseModel):
    company_name: str
    job_title: str
    location: Optional[str] = None
    status: str = "applied"
    applied_date: Optional[date] = None
    job_url: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = "normal"
    next_action_at: Optional[datetime] = None
    next_action_title: Optional[str] = None


class JobApplicationOut(BaseModel):
    id: int
    company_name: str
    job_title: str
    location: Optional[str]
    status: str
    applied_date: Optional[date]
    job_url: Optional[str]
    created_at: datetime
    updated_at: datetime
    last_activity_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    next_action_title: Optional[str] = None
    priority: str = "normal"
    tags: List[str] = []

    @field_validator("tags", mode="before")
    @classmethod
    def coerce_tags(cls, v):
        if v is None:
            return []
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                if item is None:
                    continue
                if isinstance(item, str):
                    out.append(item)
                    continue
                tag = getattr(item, "tag", None)
                if tag is None:
                    continue
                out.append(str(tag))
            return out
        return v

    @field_serializer("created_at", "updated_at", "last_activity_at", "last_action_at", "next_action_at")
    def serialize_dt(self, dt: Optional[datetime]):
        if dt is None: 
                return None
        return dt.astimezone(ET)
    
    model_config = ConfigDict(from_attributes=True)
    

class JobApplicationDetailOut(JobApplicationOut):
    notes: List[NoteOut] = []


class JobDetailsBundleOut(BaseModel):
    job: JobApplicationOut
    notes: List[NoteOut]
    interviews: List[JobInterviewOut]
    activity: JobActivityPageOut

    model_config = ConfigDict(from_attributes=True)


class JobBoardCardOut(BaseModel):
    id: int
    status: str
    company_name: str
    job_title: str
    location: Optional[str] = None
    updated_at: datetime
    last_activity_at: Optional[datetime] = None
    last_action_at: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    next_action_title: Optional[str] = None
    priority: str = "normal"
    tags: List[str] = []
    needs_follow_up: bool = False

    @field_serializer("updated_at", "last_activity_at", "last_action_at", "next_action_at")
    def serialize_dt(self, dt: Optional[datetime]):
        if dt is None:
            return None
        return dt.astimezone(ET)

    model_config = ConfigDict(from_attributes=True)


class JobsBoardOut(BaseModel):
    statuses: List[str]
    jobs: List[JobBoardCardOut]
    meta: Dict[str, Any] = {}

    model_config = ConfigDict(from_attributes=True)