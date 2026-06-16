from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolCall, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.service import AgentService
from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.core.exceptions import AppError


class ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls: list[list[LLMMessage]] = []

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        self.calls.append(messages)
        return self.responses.pop(0)


def _agent(llm: ScriptedLLM, registry: SkillRegistry, *, max_iterations: int = 4) -> AgentService:
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    return AgentService(
        llm=router,
        registry=registry,
        context=ContextManager(num_ctx=2048),
        max_tool_iterations=max_iterations,
        num_ctx=2048,
    )


def _registry(user_id: UUID) -> SkillRegistry:
    registry = SkillRegistry()

    async def handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        assert context.user_id == user_id
        return {"items": [], "args": dict(args)}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List items.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            permission_tier="read",
            handler=handler,
        )
    )
    return registry


async def test_agent_loop_executes_tool_and_returns_final_message() -> None:
    user_id = uuid4()
    llm = ScriptedLLM(
        [
            LLMResponse(
                content="",
                tool_calls=[LLMToolCall(name="list_items", arguments={"page": 1})],
            ),
            LLMResponse(content="Your drive is empty."),
        ]
    )
    agent = _agent(llm, _registry(user_id))

    response = await agent.chat(user_id=user_id, message="show files")

    assert response.message == "Your drive is empty."
    assert [call.name for call in response.tool_calls] == ["list_items"]
    assert response.tool_results[0].ok is True
    assert response.tool_results[0].output == {"items": [], "args": {"page": 1}}
    assert len(llm.calls) == 2


async def test_agent_loop_stops_at_iteration_limit() -> None:
    user_id = uuid4()
    llm = ScriptedLLM(
        [LLMResponse(content="", tool_calls=[LLMToolCall(name="list_items")]) for _ in range(2)]
    )
    agent = _agent(llm, _registry(user_id), max_iterations=1)

    with pytest.raises(AppError, match="maximum tool iteration"):
        await agent.chat(user_id=user_id, message="loop")
