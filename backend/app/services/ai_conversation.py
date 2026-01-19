from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai import AIConversation, AIConversationSummary, AIMessage
from app.models.credit import AIUsage
from app.models.user import User
from app.services.ai_usage import AIChatResult, AIUsageOrchestrator
from app.services.credits import InsufficientCreditsError
from app.services.openai_client import ChatMessage, OpenAIClient, OpenAIClientError, OpenAIUsage

PURPOSE_PROMPTS = {
    "cover_letter": (
        "You help job seekers craft persuasive, concise cover letters that match the role, emphasize results, and keep a professional tone."
    ),
    "thank_you": (
        "You write thoughtful, specific thank you notes after interviews. Reflect on the conversation, reiterate fit, and keep it warm yet concise."
    ),
    "resume_tailoring": (
        "You tailor resume bullet points using only the provided text. Highlight quantifiable impact, align to the target role, and avoid fabricating data."
    ),
}

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "You maintain a concise running summary of a job-search coaching conversation. "
    "Capture key facts, decisions, and follow-ups so the assistant remembers prior context. "
    "Keep it objective, under 200 words, and omit chit-chat."
)


class ConversationSummarizer:
    def __init__(self, *, client: OpenAIClient | None = None) -> None:
        model = settings.AI_SUMMARY_MODEL or settings.OPENAI_MODEL
        self._client = client or OpenAIClient(model=model)

    def summarize(
        self,
        *,
        previous_summary: str | None,
        new_messages: Sequence[AIMessage],
    ) -> tuple[str, OpenAIUsage]:
        if not new_messages:
            raise ValueError("new_messages must not be empty")
        transcript_lines = []
        for message in new_messages:
            label = "User" if message.role == "user" else "Assistant"
            transcript_lines.append(f"{label}: {message.content_text}")
        transcript = "\n".join(transcript_lines)
        instructions = []
        if previous_summary:
            instructions.append(f"Existing summary:\n{previous_summary.strip()}")
        instructions.append("Recent messages:\n" + transcript)
        prompt = "\n\n".join(instructions) + "\n\nUpdate the summary."
        response = self._client.chat_completion(
            messages=[
                {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            request_id=f"summary-{new_messages[-1].id}",
            max_tokens=settings.AI_SUMMARY_MAX_TOKENS,
        )
        summary_text = response.message.strip() or "Summary unavailable."
        return summary_text, response.usage


class ConversationNotFoundError(Exception):
    pass


class AIConversationService:
    def __init__(
        self,
        db: Session,
        user: User,
        *,
        orchestrator: AIUsageOrchestrator | None = None,
        summarizer: ConversationSummarizer | None = None,
    ) -> None:
        self.db = db
        self.user = user
        self.orchestrator = orchestrator or AIUsageOrchestrator(db)
        if summarizer is not None:
            self.summarizer = summarizer
        elif settings.AI_SUMMARY_MESSAGE_THRESHOLD > 0 or settings.AI_SUMMARY_TOKEN_THRESHOLD > 0:
            self.summarizer = ConversationSummarizer()
        else:
            self.summarizer = None

    def create_conversation(
        self,
        *,
        title: str | None,
        first_message: str | None,
        correlation_id: str,
        request_id: str | None = None,
        purpose: str | None = None,
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
                purpose=purpose,
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
        purpose: str | None = None,
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
        system_prompt = self._purpose_prompt(purpose)
        if system_prompt:
            context_messages = [{"role": "system", "content": system_prompt}, *context_messages]

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
            balance_remaining_cents=result.balance_cents,
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
        self._after_message_sent(conversation.id)

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
        context = [{"role": msg.role, "content": msg.content_text} for msg in history]
        summary = self._latest_summary_for_conversation_id(conversation_id)
        if summary:
            context.insert(
                0,
                {
                    "role": "system",
                    "content": f"Conversation summary (up to message #{summary.covering_message_id or 0}):\\n{summary.summary_text}",
                },
            )
        return context

    def _purpose_prompt(self, purpose: str | None) -> str | None:
        if not purpose:
            return None
        return PURPOSE_PROMPTS.get(purpose)

    def _generate_title(self, first_message: str | None) -> str | None:
        if first_message:
            snippet = first_message.strip().splitlines()[0][:80].strip()
            if snippet:
                return snippet
        return None

    def delete_conversation(self, conversation_id: int) -> None:
        conversation = self.get_conversation(conversation_id)
        self.db.delete(conversation)
        self.db.commit()

    def rename_conversation(self, conversation_id: int, title: str | None) -> AIConversation:
        conversation = self.get_conversation(conversation_id)
        conversation.title = title
        conversation.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_context_status(self, conversation: AIConversation) -> dict:
        tokens_used = self._total_estimated_tokens(conversation.id)
        budget = max(1, settings.AI_CONTEXT_TOKEN_BUDGET)
        remaining = max(0, budget - tokens_used)
        percent = min(1.0, tokens_used / budget)
        latest_summary = self._latest_summary_object(conversation)
        return {
            "token_budget": budget,
            "tokens_used": tokens_used,
            "tokens_remaining": remaining,
            "percent_used": round(percent, 4),
            "last_summarized_at": latest_summary.created_at if latest_summary else None,
        }

    def get_latest_summary(self, conversation: AIConversation) -> AIConversationSummary | None:
        return self._latest_summary_object(conversation)

    def _after_message_sent(self, conversation_id: int) -> None:
        try:
            conversation = self.db.get(AIConversation, conversation_id)
            if not conversation:
                return
            self._maybe_generate_summary(conversation)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("Conversation post-send tasks failed", extra={"conversation_id": conversation_id})

    def _maybe_generate_summary(self, conversation: AIConversation) -> None:
        if not self.summarizer:
            return
        if (
            settings.AI_SUMMARY_MESSAGE_THRESHOLD <= 0
            and settings.AI_SUMMARY_TOKEN_THRESHOLD <= 0
        ):
            return
        messages = self._conversation_messages(conversation.id)
        if settings.AI_SUMMARY_MESSAGE_THRESHOLD > 0 and len(messages) < settings.AI_SUMMARY_MESSAGE_THRESHOLD:
            return
        total_tokens = sum(self._estimate_tokens(m) for m in messages)
        if settings.AI_SUMMARY_TOKEN_THRESHOLD > 0 and total_tokens < settings.AI_SUMMARY_TOKEN_THRESHOLD:
            return
        latest_summary = self._latest_summary_object(conversation)
        last_covering_id = latest_summary.covering_message_id if latest_summary else 0
        unsummarized = [m for m in messages if not last_covering_id or m.id > last_covering_id]
        if not unsummarized:
            return
        chunk = unsummarized[: settings.AI_SUMMARY_CHUNK_SIZE]
        try:
            summary_text, usage = self.summarizer.summarize(
                previous_summary=latest_summary.summary_text if latest_summary else None,
                new_messages=chunk,
            )
        except OpenAIClientError:
            logger.warning("OpenAI summarization failed for conversation %s", conversation.id, exc_info=True)
            return
        summary = AIConversationSummary(
            conversation_id=conversation.id,
            summary_text=summary_text,
            covering_message_id=chunk[-1].id,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            total_tokens=usage.total_tokens,
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(conversation)

    def _conversation_messages(self, conversation_id: int) -> list[AIMessage]:
        return (
            self.db.query(AIMessage)
            .filter(AIMessage.conversation_id == conversation_id)
            .order_by(AIMessage.id)
            .all()
        )

    def _estimate_tokens(self, message: AIMessage) -> int:
        if message.total_tokens:
            return message.total_tokens
        if message.prompt_tokens or message.completion_tokens:
            return (message.prompt_tokens or 0) + (message.completion_tokens or 0)
        return max(1, len(message.content_text) // 4)

    def _total_estimated_tokens(self, conversation_id: int) -> int:
        return sum(self._estimate_tokens(m) for m in self._conversation_messages(conversation_id))

    def _latest_summary_for_conversation_id(self, conversation_id: int) -> AIConversationSummary | None:
        return (
            self.db.query(AIConversationSummary)
            .filter(AIConversationSummary.conversation_id == conversation_id)
            .order_by(AIConversationSummary.created_at.desc())
            .first()
        )

    def _latest_summary_object(self, conversation: AIConversation) -> AIConversationSummary | None:
        if conversation.summaries:
            return conversation.summaries[-1]
        return self._latest_summary_for_conversation_id(conversation.id)