from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.ai import AiChatRequest, AiChatResponse
from app.services.ai_usage import AIUsageExceededReservationError, AIUsageOrchestrator
from app.services.credits import CreditsService, InsufficientCreditsError, format_cents_to_dollars
from app.services.openai_client import OpenAIClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/chat", response_model=AiChatResponse)
def chat_completion(
    payload: AiChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AiChatResponse:
    request_id = payload.request_id or str(uuid.uuid4())
    credits_service = CreditsService(db)
    orchestrator = AIUsageOrchestrator(db, credits_service=credits_service)
    messages = [message.model_dump() for message in payload.messages]

    required_credits = orchestrator.estimate_reserved_credits(messages)
    current_balance = credits_service.get_balance_cents(user.id)
    if current_balance < required_credits:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits")

    try:
        result = orchestrator.run_chat(user=user, messages=messages, request_id=request_id)
    except InsufficientCreditsError:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits") from None
    except AIUsageExceededReservationError as exc:
        logger.error("AI usage exceeded reservation: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OpenAI usage exceeded reserved credits; please retry shortly.",
        ) from exc
    except OpenAIClientError as exc:
        logger.exception("OpenAI client error for request_id=%s", request_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI request failed; please retry.",
        ) from exc

    return AiChatResponse(
        request_id=result.request_id,
        model=result.model,
        response_text=result.response_text,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
        total_tokens=result.total_tokens,
        credits_used_cents=result.credits_used_cents,
        credits_refunded_cents=result.credits_refunded_cents,
        credits_reserved_cents=result.credits_reserved_cents,
        credits_remaining_cents=result.balance_cents,
        credits_remaining_dollars=format_cents_to_dollars(result.balance_cents),
    )

