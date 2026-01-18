from __future__ import annotations

import logging
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.rate_limit import require_rate_limit
from app.dependencies.request_id import get_correlation_id
from app.models.user import User
from app.models.ai import AIConversation, AIMessage
from app.schemas.ai_conversation import (
    ConversationCreateRequest,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationSummary,
    ConversationUpdateRequest,
    MessageOut,
    MessageCreateRequest,
)
from app.services.ai_conversation import AIConversationService, ConversationNotFoundError
from app.services.ai_usage import AIUsageOrchestrator
from app.services.credits import format_cents_to_dollars, InsufficientCreditsError
from app.services.limits import ConcurrencyLimitExceededError, InMemoryConcurrencyLimiter
from app.services.openai_client import OpenAIClientError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai/conversations", tags=["ai"])

_concurrency_limiter = InMemoryConcurrencyLimiter(settings.AI_MAX_CONCURRENT_REQUESTS)


def _ai_rate_limit(route_key: str):
    return Depends(
        require_rate_limit(
            route_key=route_key,
            limit=settings.AI_RATE_LIMIT_MAX_REQUESTS,
            window_seconds=settings.AI_RATE_LIMIT_WINDOW_SECONDS,
        )
    )


def get_ai_orchestrator(db: Session = Depends(get_db)) -> AIUsageOrchestrator:
    return AIUsageOrchestrator(db)


def get_ai_concurrency_limiter() -> InMemoryConcurrencyLimiter:
    return _concurrency_limiter


@router.post(
    "",
    response_model=ConversationDetailResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_ai_rate_limit("ai_conversations_create")],
)
def create_conversation(
    payload: ConversationCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
    concurrency_limiter: InMemoryConcurrencyLimiter = Depends(get_ai_concurrency_limiter),
    correlation_id: str = Depends(get_correlation_id),
) -> ConversationDetailResponse:
    service = AIConversationService(db, user, orchestrator=orchestrator)

    try:
        if payload.message:
            with concurrency_limiter.acquire(user.id):
                conversation, _ = service.create_conversation(
                    title=payload.title,
                    first_message=payload.message,
                    correlation_id=correlation_id,
                    purpose=payload.purpose,
                )
        else:
            conversation, _ = service.create_conversation(
                title=payload.title,
                first_message=None,
                correlation_id=correlation_id,
                purpose=payload.purpose,
            )
    except ConcurrencyLimitExceededError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Another AI request is already running.") from None
    except InsufficientCreditsError:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits.") from None
    except OpenAIClientError as exc:
        logger.exception("OpenAI error during conversation create")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="OpenAI request failed; please retry.") from exc

    messages, next_offset = service.get_messages(
        conversation,
        limit=min(settings.AI_MAX_CONTEXT_MESSAGES, 50),
        offset=0,
    )
    return _serialize_conversation(conversation, messages, next_offset)


@router.get(
    "",
    response_model=ConversationListResponse,
    dependencies=[_ai_rate_limit("ai_conversations_list")],
)
def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
) -> ConversationListResponse:
    service = AIConversationService(db, user, orchestrator=orchestrator)
    rows, next_offset = service.list_conversations(limit=limit, offset=offset)
    summaries = [
        ConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=message_count,
        )
        for conv, message_count in rows
    ]
    return ConversationListResponse(conversations=summaries, next_offset=next_offset)


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    dependencies=[_ai_rate_limit("ai_conversations_get")],
)
def get_conversation(
    conversation_id: int,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
) -> ConversationDetailResponse:
    service = AIConversationService(db, user, orchestrator=orchestrator)
    try:
        conversation = service.get_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None

    messages, next_offset = service.get_messages(
        conversation,
        limit=min(limit, settings.AI_MAX_CONTEXT_MESSAGES),
        offset=offset,
    )
    return _serialize_conversation(conversation, messages, next_offset)


@router.post(
    "/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[_ai_rate_limit("ai_conversations_message")],
)
def create_message(
    conversation_id: int,
    payload: MessageCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
    concurrency_limiter: InMemoryConcurrencyLimiter = Depends(get_ai_concurrency_limiter),
    correlation_id: str = Depends(get_correlation_id),
) -> ConversationMessageResponse:
    service = AIConversationService(db, user, orchestrator=orchestrator)

    try:
        conversation = service.get_conversation(conversation_id)
        with concurrency_limiter.acquire(user.id):
            user_msg, assistant_msg, result = service.send_message(
                conversation=conversation,
                content=payload.content,
                correlation_id=correlation_id,
                request_id=payload.request_id,
                purpose=payload.purpose,
            )
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    except ConcurrencyLimitExceededError:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Another AI request is already running.") from None
    except InsufficientCreditsError:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, detail="Insufficient credits.") from None
    except OpenAIClientError as exc:
        logger.exception("OpenAI error during conversation message")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail="OpenAI request failed; please retry.") from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ConversationMessageResponse(
        conversation_id=conversation.id,
        user_message=_message_to_schema(user_msg),
        assistant_message=_message_to_schema(assistant_msg),
        credits_used_cents=result.credits_used_cents,
        credits_refunded_cents=result.credits_refunded_cents,
        credits_reserved_cents=result.credits_reserved_cents,
        credits_remaining_cents=result.balance_cents,
        credits_remaining_dollars=format_cents_to_dollars(result.balance_cents),
    )


def _serialize_conversation(
    conversation: AIConversation,
    messages: Sequence[AIMessage],
    next_offset: int | None,
) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[_message_to_schema(m) for m in messages],
        next_offset=next_offset,
    )


def _message_to_schema(message: AIMessage) -> MessageOut:
    return MessageOut(
        id=message.id,
        role=message.role,
        content_text=message.content_text,
        created_at=message.created_at,
        prompt_tokens=message.prompt_tokens,
        completion_tokens=message.completion_tokens,
        total_tokens=message.total_tokens,
        credits_charged=message.credits_charged,
        model=message.model,
        balance_remaining_cents=message.balance_remaining_cents,
    )


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_ai_rate_limit("ai_conversations_delete")],
)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
) -> None:
    service = AIConversationService(db, user, orchestrator=orchestrator)
    try:
        service.delete_conversation(conversation_id)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None


@router.patch(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
    dependencies=[_ai_rate_limit("ai_conversations_update")],
)
def update_conversation(
    conversation_id: int,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    orchestrator: AIUsageOrchestrator = Depends(get_ai_orchestrator),
) -> ConversationDetailResponse:
    service = AIConversationService(db, user, orchestrator=orchestrator)
    try:
        conversation = service.rename_conversation(conversation_id, payload.title)
    except ConversationNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Conversation not found") from None
    messages, next_offset = service.get_messages(
        conversation,
        limit=min(settings.AI_MAX_CONTEXT_MESSAGES, 50),
        offset=0,
    )
    return _serialize_conversation(conversation, messages, next_offset)
