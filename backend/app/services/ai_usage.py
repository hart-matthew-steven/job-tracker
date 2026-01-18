from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Sequence

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.credit import AIUsage
from app.models.user import User
from app.services.credits import CreditsService, InsufficientCreditsError
from app.services.openai_client import ChatMessage, OpenAIClient, OpenAIClientError
import tiktoken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AIChatResult:
    usage_id: int
    request_id: str
    response_id: str
    response_text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    credits_used_cents: int
    credits_refunded_cents: int
    credits_reserved_cents: int
    balance_cents: int


class AIUsageExceededReservationError(RuntimeError):
    def __init__(self, *, reserved_cents: int, actual_cents: int, request_id: str) -> None:
        super().__init__(
            f"OpenAI usage exceeded reservation for request_id={request_id}. "
            f"reserved={reserved_cents} actual={actual_cents}"
        )
        self.reserved_cents = reserved_cents
        self.actual_cents = actual_cents
        self.request_id = request_id


class AIPricing:
    """
    Converts token usage into credits. Credits are 1:1 with integer cents (1 USD = 100 credits).
    """

    MODEL_RATES = {
        # USD cost per million tokens. Derived from OpenAI public pricing (Jan 2026).
        "gpt-4.1-mini": {
            "input_per_million_usd": Decimal("0.15"),
            "output_per_million_usd": Decimal("0.60"),
        },
    }

    def _get_rates(self, model: str) -> dict[str, Decimal]:
        return self.MODEL_RATES.get(model, self.MODEL_RATES["gpt-4.1-mini"])

    def cost_from_tokens(self, *, model: str, prompt_tokens: int, completion_tokens: int) -> int:
        rates = self._get_rates(model)
        input_cost = Decimal(prompt_tokens) * rates["input_per_million_usd"] / Decimal(1_000_000)
        output_cost = Decimal(completion_tokens) * rates["output_per_million_usd"] / Decimal(1_000_000)
        usd_total = input_cost + output_cost
        credits = math.ceil(usd_total * Decimal(100))
        if credits <= 0 and (prompt_tokens > 0 or completion_tokens > 0):
            return 1
        return max(credits, 0)

    def apply_buffer(self, base_credits: int, buffer_pct: int) -> int:
        padded = math.ceil(base_credits * (1 + buffer_pct / 100))
        return max(padded, 1) if base_credits > 0 else max(buffer_pct, 1)


class AIUsageOrchestrator:
    def __init__(
        self,
        db: Session,
        *,
        credits_service: CreditsService | None = None,
        openai_client: OpenAIClient | None = None,
        token_estimator: Callable[[Sequence[ChatMessage]], tuple[int, int]] | None = None,
    ) -> None:
        self.db = db
        self.credits = credits_service or CreditsService(db)
        self.client = openai_client or OpenAIClient()
        self.buffer_pct = settings.AI_CREDITS_RESERVE_BUFFER_PCT
        self.model = settings.OPENAI_MODEL
        self.pricing = AIPricing()
        self.max_completion_tokens = settings.AI_COMPLETION_TOKENS_MAX
        self._encoding = self._load_encoding()
        self._token_estimator = token_estimator or self._default_token_estimator

    def _load_encoding(self):
        try:
            return tiktoken.encoding_for_model(self.model)
        except KeyError:
            return tiktoken.get_encoding("cl100k_base")

    def estimate_reserved_credits(self, messages: Sequence[ChatMessage]) -> int:
        prompt_tokens, completion_tokens = self._token_estimator(messages)
        base = self.pricing.cost_from_tokens(
            model=self.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        return self.pricing.apply_buffer(base or 1, self.buffer_pct)

    def run_chat(
        self,
        *,
        user: User,
        messages: Sequence[ChatMessage],
        request_id: str | None = None,
        conversation_id: int | None = None,
        correlation_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> AIChatResult:
        request_key = request_id or str(uuid.uuid4())
        usage_record = self._get_or_create_usage(
            user_id=user.id,
            request_id=request_key,
            conversation_id=conversation_id,
            idempotency_key=idempotency_key or request_key,
        )

        if usage_record.status == "succeeded":
            logger.info(
                "ai_chat.replay",
                extra={
                    "user_id": user.id,
                    "request_id": request_key,
                    "conversation_id": usage_record.conversation_id,
                    "correlation_id": correlation_id,
                },
            )
            balance = self.credits.get_balance_cents(user.id)
            return AIChatResult(
                usage_id=usage_record.id,
                request_id=request_key,
                response_id=usage_record.response_id or request_key,
                response_text=usage_record.response_text or "",
                model=usage_record.model,
                prompt_tokens=usage_record.prompt_tokens,
                completion_tokens=usage_record.completion_tokens,
                total_tokens=usage_record.total_tokens,
                credits_used_cents=usage_record.actual_cents,
                credits_refunded_cents=usage_record.reserved_cents - usage_record.actual_cents,
                credits_reserved_cents=usage_record.reserved_cents,
                balance_cents=balance,
            )

        prompt_tokens_estimate, completion_tokens_estimate = self._token_estimator(messages)
        estimated_cost = self.pricing.cost_from_tokens(
            model=self.model,
            prompt_tokens=prompt_tokens_estimate,
            completion_tokens=completion_tokens_estimate,
        )
        base_cost = max(estimated_cost, 1)
        reserved_cents = self.pricing.apply_buffer(base_cost, self.buffer_pct)

        usage_record.feature = usage_record.feature or "ai_chat"
        usage_record.model = self.model
        usage_record.reserved_cents = reserved_cents
        usage_record.status = "reserving"
        usage_record.error_message = None
        usage_record.conversation_id = conversation_id
        self.db.flush()

        try:
            reservation = self.credits.reserve_credits(
                user_id=user.id,
                amount_cents=reserved_cents,
                idempotency_key=f"{request_key}::reserve",
                description=f"AI chat reservation ({self.model})",
                correlation_id=correlation_id,
            )
        except InsufficientCreditsError:
            usage_record.status = "failed"
            usage_record.error_message = "Insufficient credits"
            self.db.flush()
            raise

        try:
            response = self.client.chat_completion(
                messages=messages,
                request_id=request_key,
                max_tokens=self.max_completion_tokens,
            )
        except OpenAIClientError as exc:
            logger.exception("OpenAI chat failed for request_id=%s", request_key)
            self.credits.refund_reservation(
                reservation_id=reservation.reservation.id,
                user_id=user.id,
                idempotency_key=f"{request_key}::refund",
                reason="OpenAI request failed",
            )
            usage_record.status = "failed"
            usage_record.error_message = str(exc)
            self.db.commit()
            raise

        usage_record.prompt_tokens = response.usage.prompt_tokens
        usage_record.completion_tokens = response.usage.completion_tokens
        usage_record.total_tokens = response.usage.total_tokens
        usage_record.response_text = response.message

        actual_cents = self.pricing.cost_from_tokens(
            model=response.model or self.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
        )
        usage_record.actual_cents = actual_cents

        credits_refunded = 0
        if actual_cents > reserved_cents:
            delta = actual_cents - reserved_cents
            balance_after_hold = self.credits.get_balance_cents(user.id)
            if balance_after_hold < delta:
                logger.warning(
                    "ai_chat.delta_insufficient",
                    extra={
                        "user_id": user.id,
                        "conversation_id": conversation_id,
                        "request_id": request_key,
                        "reserved": reserved_cents,
                        "actual": actual_cents,
                        "correlation_id": correlation_id,
                    },
                )
                self.credits.refund_reservation(
                    reservation_id=reservation.reservation.id,
                    user_id=user.id,
                    idempotency_key=f"{request_key}::refund",
                    reason="Actual usage exceeded reservation without funds",
                )
                usage_record.status = "failed"
                usage_record.error_message = "Actual usage exceeded reservation without available credits."
                usage_record.cost_cents = 0
                self.db.commit()
                raise InsufficientCreditsError("Insufficient credits to complete AI response.")

            self.credits.finalize_charge(
                reservation_id=reservation.reservation.id,
                user_id=user.id,
                actual_amount_cents=reserved_cents,
                idempotency_key=f"{request_key}::finalize",
            )
            self.credits.spend_credits(
                user_id=user.id,
                amount_cents=delta,
                reason="ai usage delta",
                idempotency_key=f"{request_key}::delta",
            )
        else:
            self.credits.finalize_charge(
                reservation_id=reservation.reservation.id,
                user_id=user.id,
                actual_amount_cents=actual_cents,
                idempotency_key=f"{request_key}::finalize",
            )
            credits_refunded = max(reserved_cents - actual_cents, 0)

        usage_record.status = "succeeded"
        usage_record.cost_cents = actual_cents
        usage_record.error_message = None
        usage_record.response_text = response.message
        usage_record.response_id = response.response_id
        self.db.commit()

        balance = self.credits.get_balance_cents(user.id)
        return AIChatResult(
            usage_id=usage_record.id,
            request_id=request_key,
            response_id=response.response_id,
            response_text=response.message,
            model=response.model or self.model,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            credits_used_cents=actual_cents,
            credits_refunded_cents=credits_refunded,
            credits_reserved_cents=reserved_cents,
            balance_cents=balance,
        )

    def _get_or_create_usage(
        self,
        *,
        user_id: int,
        request_id: str,
        conversation_id: int | None,
        idempotency_key: str,
    ) -> AIUsage:
        usage = (
            self.db.query(AIUsage)
            .filter(AIUsage.user_id == user_id, AIUsage.request_id == request_id)
            .first()
        )
        if usage:
            if conversation_id and usage.conversation_id != conversation_id:
                usage.conversation_id = conversation_id
            return usage
        usage = AIUsage(
            user_id=user_id,
            conversation_id=conversation_id,
            feature="ai_chat",
            model=self.model,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_cents=0,
            request_id=request_id,
             response_id=None,
            idempotency_key=idempotency_key,
            reserved_cents=0,
            actual_cents=0,
            status="pending",
            response_text=None,
        )
        self.db.add(usage)
        self.db.flush()
        return usage

    def _default_token_estimator(self, messages: Sequence[ChatMessage]) -> tuple[int, int]:
        """
        Use tiktoken (same tokenizer OpenAI uses) to count prompt tokens, then reserve a fixed
        max completion budget from configuration.
        """
        prompt_tokens = 0
        for message in messages:
            content = message.get("content", "") or ""
            prompt_tokens += len(self._encoding.encode(content))
            prompt_tokens += 8  # rough overhead for role/formatting
        prompt_tokens = max(prompt_tokens, 1)
        completion_tokens = max(self.max_completion_tokens, 1)
        return prompt_tokens, completion_tokens

