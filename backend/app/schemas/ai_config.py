from __future__ import annotations

from pydantic import BaseModel


class AIConfigResponse(BaseModel):
    max_input_chars: int

