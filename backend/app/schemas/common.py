from __future__ import annotations

from pydantic import BaseModel


class MessageOut(BaseModel):
    message: str

