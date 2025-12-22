from pydantic import BaseModel, Field
from typing import Literal

ScanResult = Literal["clean", "infected", "error"]

class DocumentScanIn(BaseModel):
    document_id: int
    result: ScanResult
    detail: str | None = None  # optional message from scanner
    quarantined_s3_key: str | None = Field(default=None, description="If infected, where the object was quarantined")