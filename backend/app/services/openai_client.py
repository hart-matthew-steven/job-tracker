from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

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

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=payload_messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except OpenAIError as exc:  # pragma: no cover - handled by orchestrator tests
            raise OpenAIClientError(str(exc)) from exc

        choice = response.choices[0]
        message_content = choice.message.content or ""
        usage = response.usage or None
        usage_payload = OpenAIUsage(
            prompt_tokens=int(getattr(usage, "prompt_tokens", 0) or 0),
            completion_tokens=int(getattr(usage, "completion_tokens", 0) or 0),
            total_tokens=int(getattr(usage, "total_tokens", 0) or 0),
        )
        return OpenAIChatResponse(
            request_id=request_id,
            model=response.model or self.model,
            message=message_content,
            usage=usage_payload,
        )

