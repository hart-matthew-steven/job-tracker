from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai_config import AIConfigResponse


router = APIRouter(prefix="/ai/config", tags=["ai"])


@router.get("", response_model=AIConfigResponse)
def get_ai_config(_: User = Depends(get_current_user)) -> AIConfigResponse:
    return AIConfigResponse(max_input_chars=settings.AI_MAX_INPUT_CHARS)

