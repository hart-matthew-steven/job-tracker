from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    data: Dict[str, Any]


class SavedViewUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    data: Optional[Dict[str, Any]] = None


class SavedViewOut(BaseModel):
    id: int
    name: str
    data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


