from __future__ import annotations

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner
from app.assistant.skills.registry import RegisteredSkill, SkillRegistry


class ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        self.calls += 1
        return self.responses.pop(0)


def _registry() -> SkillRegistry:
    registry = SkillRegistry()

    async def handler(context, args):  # type: ignore[no-untyped-def]
        return {}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List items.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=handler,
        )
    )
    return registry


def _planner(llm: ScriptedLLM) -> WorkflowPlanner:
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=3,
        privacy_default="non_sensitive",
    )
    return WorkflowPlanner(
        llm=router,
        registry=_registry(),
        context=ContextManager(num_ctx=2048),
        num_ctx=2048,
    )


async def test_planner_parses_plain_json() -> None:
    llm = ScriptedLLM([LLMResponse(content='{"reply": "ok", "steps": [{"skill": "list_items"}]}')])
    result = await _planner(llm).plan(message="show files")
    assert result.reply == "ok"
    assert result.steps[0].skill == "list_items"


async def test_planner_strips_code_fences() -> None:
    content = '```json\n{"reply": "ok", "steps": []}\n```'
    result = await _planner(ScriptedLLM([LLMResponse(content=content)])).plan(message="hi")
    assert result.reply == "ok"
    assert result.steps == []


async def test_planner_repairs_invalid_json_with_retry() -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(content="not json at all"),
            LLMResponse(content='{"reply": "fixed", "steps": []}'),
        ]
    )
    result = await _planner(llm).plan(message="hi")
    assert result.reply == "fixed"
    assert llm.calls == 2
