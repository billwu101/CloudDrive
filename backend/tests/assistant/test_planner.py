from __future__ import annotations

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner, validate_plan
from app.assistant.skills.registry import RegisteredSkill, SkillRegistry
from app.assistant.workflow import PlannedStep


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
    registry.register(
        RegisteredSkill(
            name="search",
            description="Search by name.",
            parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
                "additionalProperties": True,
            },
            permission_tier="read",
            handler=handler,
        )
    )
    return registry


def _planner(llm: ScriptedLLM, *, max_repair: int = 2) -> WorkflowPlanner:
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
        max_repair=max_repair,
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


def test_validate_plan_flags_unknown_skill_and_missing_required_arg() -> None:
    registry = _registry()
    problems = validate_plan(
        [
            PlannedStep(skill="search", arguments={}),  # missing required q
            PlannedStep(skill="rm_rf", arguments={}),  # unknown skill
        ],
        registry,
    )
    assert any("missing required argument 'q'" in p for p in problems)
    assert any("unknown skill 'rm_rf'" in p for p in problems)


def test_validate_plan_accepts_complete_plan() -> None:
    problems = validate_plan([PlannedStep(skill="search", arguments={"q": "test"})], _registry())
    assert problems == []


def test_validate_plan_accepts_step_reference_for_required_arg() -> None:
    # list_items.parent_id is satisfied by a reference to step 0's output.
    steps = [
        PlannedStep(skill="search", arguments={"q": "test"}),
        PlannedStep(
            skill="list_items",
            arguments={"parent_id": {"from_step": 0, "path": "items.0.id"}},
        ),
    ]
    assert validate_plan(steps, _registry()) == []


def test_validate_plan_rejects_forward_reference() -> None:
    steps = [
        PlannedStep(
            skill="list_items",
            arguments={"parent_id": {"from_step": 1, "path": "items.0.id"}},
        ),
        PlannedStep(skill="search", arguments={"q": "test"}),
    ]
    problems = validate_plan(steps, _registry())
    assert any("must point to an earlier step" in p for p in problems)


async def test_planner_repairs_missing_required_argument() -> None:
    # First plan calls search without q (parses as JSON, but invalid) -> repair ->
    # second plan supplies q. The bad plan must never reach execution.
    llm = ScriptedLLM(
        [
            LLMResponse(content='{"reply": "searching", "steps": [{"skill": "search"}]}'),
            LLMResponse(
                content='{"reply": "searching test", "steps":'
                ' [{"skill": "search", "arguments": {"q": "test"}}]}'
            ),
        ]
    )
    result = await _planner(llm).plan(message="what is in the test folder")
    assert llm.calls == 2
    assert [s.skill for s in result.steps] == ["search"]
    assert result.steps[0].arguments == {"q": "test"}


async def test_planner_gives_up_gracefully_without_executing_invalid_plan() -> None:
    # Model keeps emitting an invalid plan; after repairs are exhausted the planner
    # must return NO steps (so nothing executes) rather than a broken call.
    bad = LLMResponse(content='{"reply": "I will search", "steps": [{"skill": "search"}]}')
    llm = ScriptedLLM([bad, bad, bad, bad])
    result = await _planner(llm, max_repair=2).plan(message="what is in the test folder")
    assert result.steps == []  # nothing to execute → no "missing argument" failure
    assert result.reply  # has a conversational explanation
    assert llm.calls == 3  # initial + 2 repairs
