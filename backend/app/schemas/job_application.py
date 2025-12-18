from datetime import date, datetime
from pydantic import BaseModel, field_serializer
from typing import Optional, List
from zoneinfo import ZoneInfo

from app.schemas.job_application_note import NoteOut

ET = ZoneInfo("America/New_York")

class JobApplicationCreate(BaseModel):
    company_name: str
    job_title: str
    location: Optional[str] = None
    status: str = "applied"
    applied_date: Optional[date] = None
    job_url: Optional[str] = None


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

    @field_serializer("created_at", "updated_at", "last_activity_at")
    def serialize_dt(self, dt: Optional[datetime]):
        if dt is None: 
                return None
        return dt.astimezone(ET)
    
    class Config:
        from_attributes = True  # pydantic v2
    

class JobApplicationDetailOut(JobApplicationOut):
    notes: List[NoteOut] = []