from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class JobActivityOut(BaseModel):
    id: int
    application_id: int
    type: str
    message: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


