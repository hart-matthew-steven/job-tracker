from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, validator


PurposeType = Literal["general", "cover_letter", "thank_you", "resume_tailoring"]


class ConversationCreateRequest(BaseModel):
    title: str | None = None
    message: str | None = None
    purpose: PurposeType | None = None

    @validator("title")
    def _strip_title(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None

    @validator("message")
    def _strip_message(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        return value or None


class ConversationSummary(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    conversations: list[ConversationSummary]
    next_offset: int | None = None


class MessageOut(BaseModel):
    id: int
    role: str
    content_text: str
    created_at: datetime
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    credits_charged: int | None = None
    model: str | None = None
    balance_remaining_cents: int | None = None


class ConversationDetailResponse(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut]
    next_offset: int | None = None


class MessageCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    request_id: str | None = None
    purpose: PurposeType | None = None

    @validator("content")
    def _strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be empty")
        return value


class ConversationUpdateRequest(BaseModel):
    title: str | None = None

    @validator("title")
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class ConversationMessageResponse(BaseModel):
    conversation_id: int
    user_message: MessageOut
    assistant_message: MessageOut
    credits_used_cents: int
    credits_refunded_cents: int
    credits_reserved_cents: int
    credits_remaining_cents: int
    credits_remaining_dollars: str


