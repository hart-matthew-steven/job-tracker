from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.admin import require_admin_user
from app.models.user import User
from app.schemas.admin_rate_limits import (
    RateLimitOverrideRequest,
    RateLimitOverrideResponse,
    RateLimitRecordSchema,
    RateLimitResetRequest,
    RateLimitResetResponse,
    RateLimitStatusResponse,
)
from app.services.rate_limit_admin import (
    RateLimitAdminError,
    RateLimitAdminService,
    RateLimitRecord,
)

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/admin/rate-limits", tags=["admin"])


def get_rate_limit_admin_service() -> RateLimitAdminService:
    try:
        return RateLimitAdminService()
    except RateLimitAdminError as exc:
        logger.error("Rate limit admin service unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Rate limiting admin tools are unavailable",
        ) from exc


@router.get(
    "/status",
    response_model=RateLimitStatusResponse,
)
def get_status(
    user_id: int = Query(..., gt=0),
    _admin_user: User = Depends(require_admin_user),
    service: RateLimitAdminService = Depends(get_rate_limit_admin_service),
) -> RateLimitStatusResponse:
    records = service.list_user_limits(user_id=user_id)
    return RateLimitStatusResponse(
        user_id=user_id,
        records=[_record_to_schema(r) for r in records],
    )


@router.post(
    "/reset",
    response_model=RateLimitResetResponse,
    status_code=status.HTTP_200_OK,
)
def reset_limits(
    payload: RateLimitResetRequest,
    _admin_user: User = Depends(require_admin_user),
    service: RateLimitAdminService = Depends(get_rate_limit_admin_service),
) -> RateLimitResetResponse:
    deleted = service.reset_user_limits(user_id=payload.user_id)
    return RateLimitResetResponse(user_id=payload.user_id, deleted=deleted)


@router.post(
    "/override",
    response_model=RateLimitOverrideResponse,
    status_code=status.HTTP_200_OK,
)
def override_limits(
    payload: RateLimitOverrideRequest,
    _admin_user: User = Depends(require_admin_user),
    service: RateLimitAdminService = Depends(get_rate_limit_admin_service),
) -> RateLimitOverrideResponse:
    try:
        expires_at = service.apply_override(
            user_id=payload.user_id,
            limit=payload.limit,
            window_seconds=payload.window_seconds,
            ttl_seconds=payload.ttl_seconds,
        )
    except RateLimitAdminError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RateLimitOverrideResponse(
        user_id=payload.user_id,
        limit=payload.limit,
        window_seconds=payload.window_seconds,
        expires_at=expires_at,
    )


def _record_to_schema(record: RateLimitRecord) -> RateLimitRecordSchema:
    return RateLimitRecordSchema(
        limiter_key=record.limiter_key,
        window_seconds=record.window_seconds,
        limit=record.limit,
        count=record.count,
        remaining=record.remaining,
        expires_at=record.expires_at,
        record_type=record.record_type,
    )
