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
    # ``chat(target=...)`` forcing values. ``"local"`` uses only the local model;
    # an external provider name (e.g. ``"openai"``/``"codex"``) uses only that
    # external client. ``None`` keeps the default local→external fallback (DEC-023).
    LOCAL_TARGET = "local"

    def __init__(
        self,
        *,
        local_client: LLMClient,
        external_client: LLMClient | None,
        external_enabled: bool,
        max_local_attempts: int,
        privacy_default: PrivacyDefault,
        external_clients: dict[str, LLMClient] | None = None,
    ) -> None:
        self._local = local_client
        self._external = external_client
        self._external_enabled = external_enabled
        self._max_local_attempts = max(1, max_local_attempts)
        self._privacy_default = privacy_default
        # Per-provider external clients for explicit selection (model-selection
        # feature). Empty means only the default fallback client is available.
        self._external_clients = external_clients or {}

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        validator: ResponseValidator | None = None,
        target: str | None = None,
    ) -> LLMResponse:
        # Explicit external provider: use only that client — no local attempt and
        # no fallback. Selecting it is itself the user's opt-in to externalize.
        if target is not None and target != self.LOCAL_TARGET:
            client = self._external_clients.get(target) or self._external
            if client is None:
                raise LLMUnavailableError(f"Selected model '{target}' is not configured")
            return await self._call_external(
                client, messages, tools, num_ctx=num_ctx, last_error=None
            )

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

        # Explicit local target: no fallback — surface the local failure plainly.
        if target == self.LOCAL_TARGET:
            raise LLMUnavailableError("Local model is unavailable") from last_error

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
        return await self._call_external(
            self._external, messages, tools, num_ctx=num_ctx, last_error=last_error
        )

    async def _call_external(
        self,
        client: LLMClient,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        last_error: Exception | None,
    ) -> LLMResponse:
        joined = "\n".join(m.content for m in messages)
        privacy = classify_and_deidentify(joined, default=self._privacy_default)
        if privacy.is_sensitive and not privacy.deidentified:
            raise LLMUnavailableError(
                "Cannot send privacy-sensitive content to an external model"
            ) from last_error

        external_messages = messages
        if privacy.deidentified:
            external_messages = [LLMMessage(role="user", content=privacy.text_for_external)]
        return await client.chat(external_messages, tools, num_ctx=num_ctx)
