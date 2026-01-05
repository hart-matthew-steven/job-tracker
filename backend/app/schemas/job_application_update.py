from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobApplicationUpdate(BaseModel):
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    priority: Optional[str] = None
    next_action_at: Optional[datetime] = None
    next_action_title: Optional[str] = None
    last_action_at: Optional[datetime] = None