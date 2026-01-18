from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Sequence

from openai import OpenAI, OpenAIError

from app.core.config import settings


ChatMessage = dict[str, str]


@dataclass(frozen=True)
class OpenAIUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(frozen=True)
class OpenAIChatResponse:
    request_id: str
    response_id: str
    model: str
    message: str
    usage: OpenAIUsage


class OpenAIClientError(RuntimeError):
    pass


class OpenAIClient:
    """
    Thin wrapper around the OpenAI SDK so the rest of the app can be unit-tested
    without importing the global client module.
    """

    def __init__(self, *, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or settings.OPENAI_API_KEY
        if not key:
            raise OpenAIClientError("OPENAI_API_KEY is not configured")
        self.model = model or settings.OPENAI_MODEL
        if not self.model:
            raise OpenAIClientError("OPENAI_MODEL is not configured")
        self._client = OpenAI(api_key=key)
        self.max_retries = settings.AI_OPENAI_MAX_RETRIES

    def chat_completion(
        self,
        *,
        messages: Sequence[ChatMessage],
        request_id: str,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> OpenAIChatResponse:
        payload_messages = [
            {"role": message["role"], "content": message["content"]}
            for message in messages
            if message.get("role") and message.get("content")
        ]
        if not payload_messages:
            raise OpenAIClientError("At least one chat message is required")

        last_exc: OpenAIError | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=payload_messages,  # type: ignore[arg-type]
                    temperature=temperature,
                    max_tokens=max_tokens,
                    extra_headers={"X-Request-ID": request_id},
                )
                break
            except OpenAIError as exc:  # pragma: no cover - retry logic tested separately
                last_exc = exc
                if attempt == self.max_retries or not self._is_retryable(exc):
                    raise OpenAIClientError(str(exc)) from exc
                backoff = min(0.5 * (2 ** (attempt - 1)), 5.0)
                time.sleep(backoff + random.uniform(0, 0.25))
        else:  # pragma: no cover - defensive
            raise OpenAIClientError(str(last_exc) if last_exc else "Unknown OpenAI error")

        choice = response.choices[0]
        message_content = choice.message.content or ""
        usage = response.usage or None
        usage_payload = OpenAIUsage(
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )
        response_id = getattr(response, "id", None) or getattr(getattr(response, "response_metadata", {}), "request_id", None)
        return OpenAIChatResponse(
            request_id=request_id,
            response_id=response_id or request_id,
            model=response.model or self.model,
            message=message_content,
            usage=usage_payload,
        )

    def _is_retryable(self, exc: OpenAIError) -> bool:
        status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
        if isinstance(status, int):
            return status >= 500 or status in {408, 429}
        message = str(exc).lower()
        return "timeout" in message or "temporarily unavailable" in message

