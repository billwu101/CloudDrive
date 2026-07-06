from __future__ import annotations

from typing import Any

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
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        raise LLMUnavailableError("no model")


class SuccessfulLLM:
    def __init__(self, content: str = "external success") -> None:
        self.calls = 0
        self._content = content

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(content=self._content)


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


async def test_target_local_does_not_fall_back_to_external() -> None:
    local = FailingLLM()
    external = SuccessfulLLM()
    router = ModelRouter(
        local_client=local,
        external_client=external,
        external_enabled=True,
        max_local_attempts=2,
        privacy_default="non_sensitive",
    )

    try:
        await router.chat(
            [LLMMessage(role="user", content="hello")], [], num_ctx=128, target="local"
        )
    except LLMUnavailableError:
        pass
    else:
        raise AssertionError("Expected local-only failure")

    assert local.calls == 2
    assert external.calls == 0  # never escalates when local is explicitly chosen


async def test_target_external_skips_local_and_picks_provider() -> None:
    local = SuccessfulLLM(content="local")
    openai = SuccessfulLLM(content="openai")
    codex = SuccessfulLLM(content="codex")
    router = ModelRouter(
        local_client=local,
        external_client=None,
        external_enabled=False,  # no global fallback; selection is the opt-in
        max_local_attempts=2,
        privacy_default="non_sensitive",
        external_clients={"openai": openai, "codex": codex},
    )

    response = await router.chat(
        [LLMMessage(role="user", content="hi")], [], num_ctx=128, target="openai"
    )

    assert response.content == "openai"
    assert local.calls == 0  # local is never tried when an external model is chosen
    assert openai.calls == 1
    assert codex.calls == 0


async def test_target_external_not_configured_raises() -> None:
    router = ModelRouter(
        local_client=SuccessfulLLM(),
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )

    try:
        await router.chat([LLMMessage(role="user", content="hi")], [], num_ctx=128, target="openai")
    except LLMUnavailableError as exc:
        assert "not configured" in str(exc)
    else:
        raise AssertionError("Expected not-configured failure")


class CapturingLLM:
    def __init__(self) -> None:
        self.response_format: dict[str, Any] | None = None

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        self.response_format = response_format
        return LLMResponse(content="ok")


async def test_response_format_forwarded_to_external() -> None:
    external = CapturingLLM()
    router = ModelRouter(
        local_client=FailingLLM(),
        external_client=external,
        external_enabled=True,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    schema = {"type": "json_schema", "json_schema": {"name": "plan", "schema": {}}}

    await router.chat(
        [LLMMessage(role="user", content="hi")], [], num_ctx=128, response_format=schema
    )

    assert external.response_format == schema
