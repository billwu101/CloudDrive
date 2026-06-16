"""Property-based ("fuzz") tests for the assistant pipeline.

Users send complex prompts that combine multiple skills, chain step outputs,
or ask for capabilities that do not exist. A small local model will sometimes
emit malformed plans. These tests assert the hard safety invariants under
*randomised* input: the pipeline must never crash and must never execute an
invalid plan, no matter what the model produces.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any
from uuid import uuid4

from hypothesis import given, settings
from hypothesis import strategies as st

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.permissions import classify_steps
from app.assistant.planner import WorkflowPlanner, validate_plan
from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.assistant.workflow import (
    READ_TIER,
    PlannedStep,
    StepResolutionError,
    StepResult,
    WorkflowExecutor,
    WorkflowStep,
    is_step_ref,
    resolve_arguments,
)
from app.core.exceptions import AppError

# A fixed catalog of known skills: name -> (permission_tier, required_args).
KNOWN: dict[str, tuple[str, list[str]]] = {
    "list_items": ("read", []),
    "search": ("read", ["q"]),
    "create_folder": ("write", ["name"]),
    "trash_item": ("destructive", ["item_id"]),
}


def build_registry() -> SkillRegistry:
    registry = SkillRegistry()

    async def handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        # Some inputs intentionally make handlers raise (e.g. bad types); the
        # executor must turn that into a failed step, never propagate it.
        if args.get("explode") is True:
            raise RuntimeError("boom")
        return {"items": [{"id": "ITEM-1", "name": "n"}], "total": 1, "echo": dict(args)}

    for name, (tier, required) in KNOWN.items():
        registry.register(
            RegisteredSkill(
                name=name,
                description=name,
                parameters={
                    "type": "object",
                    "properties": {},
                    "required": required,
                    "additionalProperties": True,
                },
                permission_tier=tier,
                handler=handler,
            )
        )
    return registry


# --- Strategies -------------------------------------------------------------

literal_values = st.one_of(st.text(max_size=8), st.integers(-3, 3), st.booleans(), st.none())
ref_values = st.fixed_dictionaries(
    {
        "from_step": st.integers(min_value=-2, max_value=6),
        "path": st.sampled_from(
            ["items.0.id", "items.0.name", "total", "bad.path", "items.9.id", ""]
        ),
    }
)
arg_values = st.one_of(literal_values, ref_values)
argument_dicts = st.dictionaries(
    st.sampled_from(["q", "name", "item_id", "parent_id", "explode", "x"]),
    arg_values,
    max_size=4,
)
# Skill names: a mix of known skills and entirely made-up ("non-built-in") ones.
skill_names = st.one_of(
    st.sampled_from(sorted(KNOWN)), st.text(alphabet="abcdef_", min_size=1, max_size=6)
)
planned_steps = st.lists(
    st.builds(lambda s, a: PlannedStep(skill=s, arguments=a), skill_names, argument_dicts),
    max_size=6,
)


def _to_workflow_steps(steps: list[PlannedStep]) -> list[WorkflowStep]:
    return [
        WorkflowStep(
            index=i,
            skill=s.skill,
            arguments=s.arguments,
            permission_tier=READ_TIER,
            requires_approval=False,
        )
        for i, s in enumerate(steps)
    ]


# --- Properties -------------------------------------------------------------


@settings(max_examples=300, deadline=None)
@given(planned_steps)
def test_validate_plan_is_total_and_sound(steps: list[PlannedStep]) -> None:
    registry = build_registry()
    problems = validate_plan(steps, registry)  # must never raise
    assert isinstance(problems, list)
    if problems == []:
        # Soundness: an accepted plan only references known skills, supplies every
        # required argument (literal or backward reference), and never forward-refs.
        for index, step in enumerate(steps):
            assert step.skill in KNOWN
            for required in KNOWN[step.skill][1]:
                value = step.arguments.get(required)
                present = value is not None and not (isinstance(value, str) and not value.strip())
                assert present or is_step_ref(value)
            for value in step.arguments.values():
                if is_step_ref(value):
                    from_step = value.get("from_step")
                    assert isinstance(from_step, int) and 0 <= from_step < index


@settings(max_examples=200, deadline=None)
@given(planned_steps)
def test_executor_never_raises_and_stops_on_first_failure(steps: list[PlannedStep]) -> None:
    registry = build_registry()
    executor = WorkflowExecutor(registry=registry)
    results = asyncio.run(executor.execute(user_id=uuid4(), steps=_to_workflow_steps(steps)))

    assert isinstance(results, list)
    assert len(results) <= len(steps)
    failures = [i for i, r in enumerate(results) if not r.ok]
    # At most one failure, and it is the last result (execution stops on error).
    if failures:
        assert failures == [len(results) - 1]


@settings(max_examples=300, deadline=None)
@given(argument_dicts, st.integers(min_value=0, max_value=5))
def test_resolve_arguments_only_raises_resolution_error(
    arguments: dict[str, Any], result_count: int
) -> None:
    results_by_index = {
        i: StepResult(index=i, skill="s", ok=True, output={"items": [{"id": "X"}], "total": 1})
        for i in range(result_count)
    }
    try:
        resolved = resolve_arguments(arguments, results_by_index)
    except StepResolutionError:
        return  # the only acceptable failure mode
    assert set(resolved.keys()) == set(arguments.keys())


@settings(max_examples=200, deadline=None)
@given(planned_steps)
def test_classify_steps_tiers_or_rejects_unknown(steps: list[PlannedStep]) -> None:
    registry = build_registry()
    try:
        classified = classify_steps(steps, registry)
    except AppError:
        # Raised only when a step references an unknown skill or forward dependency.
        assert any(s.skill not in KNOWN for s in steps) or any(s.depends_on for s in steps)
        return
    for step in classified:
        assert step.requires_approval == (step.permission_tier != READ_TIER)


class _ScriptedLLM:
    def __init__(self, plans: list[dict[str, Any]]) -> None:
        self._plans = plans
        self._index = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        plan = self._plans[min(self._index, len(self._plans) - 1)]
        self._index += 1
        return LLMResponse(content=json.dumps(plan))


plan_payloads = st.lists(
    st.fixed_dictionaries(
        {
            "reply": st.text(max_size=6),
            "steps": st.lists(
                st.fixed_dictionaries({"skill": skill_names, "arguments": argument_dicts}),
                max_size=4,
            ),
        }
    ),
    min_size=1,
    max_size=4,
)


@settings(max_examples=200, deadline=None)
@given(plan_payloads)
def test_planner_output_is_always_executable_or_empty(plans: list[dict[str, Any]]) -> None:
    registry = build_registry()
    router = ModelRouter(
        local_client=_ScriptedLLM(plans),
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    planner = WorkflowPlanner(
        llm=router,
        registry=registry,
        context=ContextManager(num_ctx=2048),
        num_ctx=2048,
        max_repair=2,
    )
    result = asyncio.run(planner.plan(message="a complex multi-step request"))
    # The planner must never hand back an invalid plan: either it is clean
    # (safe to execute) or it has no steps (answered conversationally).
    assert result.steps == [] or validate_plan(result.steps, registry) == []
