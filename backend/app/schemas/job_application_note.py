from datetime import datetime
from pydantic import BaseModel, field_serializer
from zoneinfo import ZoneInfo
from typing import Optional

ET = ZoneInfo("America/New_York")

class NoteCreate(BaseModel):
    body: str


class NoteOut(BaseModel):
    id: int
    application_id: int
    body: str
    created_at: datetime

    @field_serializer("created_at")
    def serialize_dt(self, dt: Optional[datetime]):
        if dt is None: 
            return None
        return dt.astimezone(ET)

    class Config:
        from_attributes = True