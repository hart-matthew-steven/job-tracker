from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.config import settings
from app.models.ai import AIConversation, AIMessage
from app.models.credit import AIUsage
from app.models.user import User
from app.services.ai_usage import AIChatResult, AIUsageOrchestrator
from app.services.credits import InsufficientCreditsError
from app.services.openai_client import ChatMessage


class ConversationNotFoundError(Exception):
    pass


class AIConversationService:
    def __init__(
        self,
        db: Session,
        user: User,
        *,
        orchestrator: AIUsageOrchestrator | None = None,
    ) -> None:
        self.db = db
        self.user = user
        self.orchestrator = orchestrator or AIUsageOrchestrator(db)

    def create_conversation(
        self,
        *,
        title: str | None,
        first_message: str | None,
        correlation_id: str,
        request_id: str | None = None,
    ) -> tuple[AIConversation, list[AIMessage]]:
        conversation = AIConversation(
            user_id=self.user.id,
            title=title or self._generate_title(first_message),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(conversation)
        self.db.flush()

        messages: list[AIMessage] = []
        if first_message:
            user_msg, assistant_msg, _ = self.send_message(
                conversation=conversation,
                content=first_message,
                correlation_id=correlation_id,
                request_id=request_id,
            )
            messages = [user_msg, assistant_msg]
        else:
            self.db.commit()

        return conversation, messages

    def list_conversations(self, *, limit: int, offset: int) -> tuple[list[tuple[AIConversation, int]], int | None]:
        subquery = (
            self.db.query(
                AIConversation,
                func.count(AIMessage.id).label("message_count"),
            )
            .outerjoin(AIMessage, AIMessage.conversation_id == AIConversation.id)
            .filter(AIConversation.user_id == self.user.id)
            .group_by(AIConversation.id)
            .order_by(AIConversation.updated_at.desc(), AIConversation.id.desc())
            .offset(offset)
            .limit(limit + 1)
        )
        rows = subquery.all()
        next_offset = offset + limit if len(rows) > limit else None
        return rows[:limit], next_offset

    def get_conversation(self, conversation_id: int) -> AIConversation:
        conversation = self.db.get(AIConversation, conversation_id)
        if not conversation or conversation.user_id != self.user.id:
            raise ConversationNotFoundError("Conversation not found")
        return conversation

    def get_messages(
        self,
        conversation: AIConversation,
        *,
        limit: int,
        offset: int,
    ) -> tuple[list[AIMessage], int | None]:
        query = (
            self.db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation.id)
            .order_by(AIMessage.created_at, AIMessage.id)
            .offset(offset)
            .limit(limit + 1)
        )
        rows = query.all()
        next_offset = offset + limit if len(rows) > limit else None
        return rows[:limit], next_offset

    def send_message(
        self,
        conversation: AIConversation,
        *,
        content: str,
        correlation_id: str,
        request_id: str | None = None,
    ) -> tuple[AIMessage, AIMessage, AIChatResult]:
        if conversation.user_id != self.user.id:
            raise ConversationNotFoundError("Conversation not found")
        content = content.strip()
        if not content:
            raise ValueError("Message content cannot be empty.")
        if len(content) > settings.AI_MAX_INPUT_CHARS:
            raise ValueError("Message exceeds the maximum allowed length.")

        user_message = AIMessage(
            conversation_id=conversation.id,
            role="user",
            content_text=content,
        )
        self.db.add(user_message)
        self.db.flush()

        context_messages = self._build_context(conversation.id, user_message)

        try:
            result = self.orchestrator.run_chat(
                user=self.user,
                messages=context_messages,
                request_id=request_id,
                conversation_id=conversation.id,
                correlation_id=correlation_id,
            )
        except InsufficientCreditsError:
            self.db.rollback()
            raise

        assistant_message = AIMessage(
            conversation_id=conversation.id,
            role="assistant",
            content_text=result.response_text,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            total_tokens=result.total_tokens,
            credits_charged=result.credits_used_cents,
            model=result.model,
            request_id=result.response_id,
        )
        self.db.add(assistant_message)
        self.db.flush()

        usage = self.db.get(AIUsage, result.usage_id)
        if usage:
            usage.message_id = assistant_message.id
            usage.conversation_id = conversation.id
            usage.cost_cents = result.credits_used_cents
            usage.response_text = result.response_text

        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()

        return user_message, assistant_message, result

    def _build_context(self, conversation_id: int, latest_message: AIMessage) -> Sequence[ChatMessage]:
        rows: Iterable[AIMessage] = (
            self.db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation_id, AIMessage.id != latest_message.id)
            .order_by(AIMessage.created_at.desc(), AIMessage.id.desc())
            .limit(max(0, settings.AI_MAX_CONTEXT_MESSAGES - 1))
            .all()
        )
        history = list(reversed(rows))
        history.append(latest_message)
        return [{"role": msg.role, "content": msg.content_text} for msg in history]

    def _generate_title(self, first_message: str | None) -> str | None:
        if first_message:
            snippet = first_message.strip().splitlines()[0][:80].strip()
            if snippet:
                return snippet
        return None

