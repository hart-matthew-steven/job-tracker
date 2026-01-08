from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class RateLimitRecordSchema(BaseModel):
    limiter_key: str
    window_seconds: int
    limit: int
    count: int
    remaining: int
    expires_at: int
    record_type: Literal["counter", "override"]


class RateLimitStatusResponse(BaseModel):
    user_id: int
    records: list[RateLimitRecordSchema]


class RateLimitResetRequest(BaseModel):
    user_id: int = Field(..., gt=0)


class RateLimitResetResponse(BaseModel):
    user_id: int
    deleted: int


class RateLimitOverrideRequest(BaseModel):
    user_id: int = Field(..., gt=0)
    limit: int = Field(..., gt=0)
    window_seconds: int = Field(..., gt=0)
    ttl_seconds: int = Field(..., gt=0)


class RateLimitOverrideResponse(BaseModel):
    user_id: int
    limit: int
    window_seconds: int
    expires_at: int
