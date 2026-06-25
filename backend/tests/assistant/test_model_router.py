from __future__ import annotations

from app.assistant.llm.client import (
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
    LLMUnavailableError,
)
from app.assistant.llm.router import ModelRouter


class FailingLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        self.calls += 1
        raise LLMUnavailableError("no model")


class SuccessfulLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(content="external success")


async def test_model_router_escalates_after_local_failures() -> None:
    local = FailingLLM()
    external = SuccessfulLLM()
    router = ModelRouter(
        local_client=local,
        external_client=external,
        external_enabled=True,
        max_local_attempts=2,
        privacy_default="non_sensitive",
    )

    response = await router.chat([LLMMessage(role="user", content="hello")], [], num_ctx=128)

    assert response.content == "external success"
    assert local.calls == 2
    assert external.calls == 1


async def test_model_router_blocks_external_when_privacy_sensitive() -> None:
    local = FailingLLM()
    external = SuccessfulLLM()
    router = ModelRouter(
        local_client=local,
        external_client=external,
        external_enabled=True,
        max_local_attempts=2,
        privacy_default="sensitive",
    )

    try:
        await router.chat(
            [LLMMessage(role="user", content="private file request")], [], num_ctx=128
        )
    except LLMUnavailableError as exc:
        assert "privacy-sensitive" in str(exc)
    else:
        raise AssertionError("Expected privacy-sensitive failure")

    assert local.calls == 2
    assert external.calls == 0
