from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(..., min_length=1)


class AiChatRequest(BaseModel):
    messages: list[ChatMessage]
    request_id: str | None = None

    @field_validator("messages")
    @classmethod
    def _ensure_messages(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if not value:
            raise ValueError("messages must not be empty")
        return value


class AiChatResponse(BaseModel):
    request_id: str
    model: str
    response_text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    credits_used_cents: int
    credits_refunded_cents: int
    credits_reserved_cents: int
    credits_remaining_cents: int
    credits_remaining_dollars: str

