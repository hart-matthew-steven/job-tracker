from pydantic import BaseModel
from typing import Literal

ScanResult = Literal["clean", "infected", "error"]

class DocumentScanIn(BaseModel):
    document_id: int
    result: ScanResult
    detail: str | None = None  # optional message from scanner