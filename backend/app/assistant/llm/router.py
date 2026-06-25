from __future__ import annotations

from collections.abc import Callable

from app.assistant.llm.client import (
    LLMClient,
    LLMClientError,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
    LLMUnavailableError,
)
from app.assistant.llm.privacy import PrivacyDefault, classify_and_deidentify

ResponseValidator = Callable[[LLMResponse], bool]


class ModelRouter:
    def __init__(
        self,
        *,
        local_client: LLMClient,
        external_client: LLMClient | None,
        external_enabled: bool,
        max_local_attempts: int,
        privacy_default: PrivacyDefault,
    ) -> None:
        self._local = local_client
        self._external = external_client
        self._external_enabled = external_enabled
        self._max_local_attempts = max(1, max_local_attempts)
        self._privacy_default = privacy_default

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        validator: ResponseValidator | None = None,
    ) -> LLMResponse:
        last_error: Exception | None = None
        for _ in range(self._max_local_attempts):
            try:
                response = await self._local.chat(messages, tools, num_ctx=num_ctx)
            except LLMClientError as exc:
                last_error = exc
                continue
            if validator is None or validator(response):
                return response
            last_error = LLMUnavailableError("Local model response did not pass validation")

        return await self._try_external(messages, tools, num_ctx=num_ctx, last_error=last_error)

    async def _try_external(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        last_error: Exception | None,
    ) -> LLMResponse:
        if not self._external_enabled or self._external is None:
            raise LLMUnavailableError("Local model failed and external fallback is disabled") from (
                last_error
            )

        joined = "\n".join(m.content for m in messages)
        privacy = classify_and_deidentify(joined, default=self._privacy_default)
        if privacy.is_sensitive and not privacy.deidentified:
            raise LLMUnavailableError(
                "Local model failed and privacy-sensitive content cannot be externalized"
            ) from last_error

        external_messages = messages
        if privacy.deidentified:
            external_messages = [LLMMessage(role="user", content=privacy.text_for_external)]
        return await self._external.chat(external_messages, tools, num_ctx=num_ctx)
