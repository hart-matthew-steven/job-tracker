from pydantic import BaseModel
from typing import Optional

class JobApplicationUpdate(BaseModel):
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    location: Optional[str] = None
    job_url: Optional[str] = None
    status: Optional[str] = None