from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from app.assistant.permissions import classify_steps
from app.assistant.planner import validate_plan
from app.assistant.skills.registry import RegisteredSkill, SkillRegistry
from app.assistant.workflow import (
    PlannedStep,
    StepResolutionError,
    StepResult,
    apply_selection,
    has_selection_reference,
    is_selection_ref,
    is_step_ref,
    resolve_arguments,
)


async def _noop(ctx: object, args: object) -> None:
    return None


def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        RegisteredSkill(
            name="search",
            description="read",
            parameters={"type": "object", "properties": {"q": {"type": "string"}}},
            permission_tier="read",
            handler=_noop,
        )
    )
    registry.register(
        RegisteredSkill(
            name="move_item",
            description="move",
            parameters={
                "type": "object",
                "properties": {"item_id": {"type": "string"}, "parent_id": {}},
                "required": ["item_id"],
            },
            permission_tier="write",
            handler=_noop,
        )
    )
    registry.register(
        RegisteredSkill(
            name="list_items",
            description="read",
            parameters={"type": "object", "properties": {}},
            permission_tier="read",
            handler=_noop,
        )
    )
    registry.register(
        RegisteredSkill(
            name="compress_to_zip",
            description="self-built",
            parameters={"type": "object", "properties": {"item_id": {"type": "string"}}},
            permission_tier="write",
            handler=_noop,
            requires_selection=True,
        )
    )
    return registry


def _sel(ids: list[str]) -> list[dict[str, Any]]:
    return [{"id": i, "name": f"file-{n}", "item_type": "FILE"} for n, i in enumerate(ids)]


# --- reference predicates -------------------------------------------------


def test_reference_predicates_distinguish_selection_and_step() -> None:
    assert is_selection_ref({"from": "selection", "item": 0}) is True
    assert is_selection_ref({"from": "selection", "each": True}) is True
    assert is_selection_ref({"from": 0, "path": "items.0.id"}) is False
    assert is_step_ref({"from": 2, "path": "items.0.id"}) is True
    assert is_step_ref({"from_step": 2, "path": "items.0.id"}) is True  # legacy
    assert is_step_ref({"from": "selection"}) is False
    assert is_step_ref({"from": True}) is False  # bool is not a step index


# --- apply_selection: single reference, preserving other arguments --------


def test_apply_selection_single_item_preserves_other_args() -> None:
    registry = _registry()
    a, b = str(uuid4()), str(uuid4())
    planned = [
        PlannedStep(skill="search", arguments={"q": "test2"}),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": "selection", "item": 1},
                "parent_id": {"from": 0, "path": "items.0.id"},
            },
            depends_on=[0],
        ),
    ]
    steps = classify_steps(planned, registry)

    out = apply_selection(steps, _sel([a, b]), registry)

    assert len(out) == 2
    move = out[1]
    assert move.arguments["item_id"] == b  # item index 1
    # the step-output reference for the destination is preserved untouched
    assert move.arguments["parent_id"] == {"from": 0, "path": "items.0.id"}
    assert move.depends_on == [0]


# --- apply_selection: `each` fan-out (the multi-file move fix) -------------


def test_apply_selection_each_fans_out_and_keeps_destination() -> None:
    registry = _registry()
    ids = [str(uuid4()) for _ in range(3)]
    planned = [
        PlannedStep(skill="search", arguments={"q": "test2"}),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": "selection", "each": True},
                "parent_id": {"from": 0, "path": "items.0.id"},
            },
            depends_on=[0],
        ),
    ]
    steps = classify_steps(planned, registry)

    out = apply_selection(steps, _sel(ids), registry)

    # 1 search + 3 moves, re-indexed 0..3
    assert [s.index for s in out] == [0, 1, 2, 3]
    moves = out[1:]
    assert [m.arguments["item_id"] for m in moves] == ids  # one per selected file
    # every fanned-out move keeps the SAME destination reference (the bug fix)
    for m in moves:
        assert m.arguments["parent_id"] == {"from": 0, "path": "items.0.id"}
        assert m.depends_on == [0]
        assert m.requires_approval is True  # write tier still needs confirm


def test_apply_selection_out_of_range_index_raises() -> None:
    registry = _registry()
    planned = [
        PlannedStep(skill="move_item", arguments={"item_id": {"from": "selection", "item": 5}}),
    ]
    steps = classify_steps(planned, registry)

    with pytest.raises(StepResolutionError):
        apply_selection(steps, _sel([str(uuid4())]), registry)


# --- requires_selection sugar + dependency remap --------------------------


def test_requires_selection_sugar_runs_once_per_file() -> None:
    registry = _registry()
    ids = [str(uuid4()), str(uuid4())]
    # planner leaves item_id unbound; sugar binds it to the whole selection
    planned = [PlannedStep(skill="compress_to_zip")]
    steps = classify_steps(planned, registry)

    out = apply_selection(steps, _sel(ids), registry)

    assert [s.arguments["item_id"] for s in out] == ids
    assert all(s.requires_approval for s in out)


def test_fan_out_remaps_downstream_dependencies() -> None:
    registry = _registry()
    ids = [str(uuid4()), str(uuid4())]
    planned = [
        PlannedStep(skill="compress_to_zip"),  # index 0 → fans into 0,1
        PlannedStep(skill="list_items", depends_on=[0]),  # trailing read
    ]
    steps = classify_steps(planned, registry)

    out = apply_selection(steps, _sel(ids), registry)

    assert [s.index for s in out] == [0, 1, 2]
    # the read step now depends on BOTH fanned-out compress steps
    assert sorted(out[-1].depends_on) == [0, 1]


# --- has_selection_reference ---------------------------------------------


def test_has_selection_reference_detects_both_forms() -> None:
    registry = _registry()
    explicit = classify_steps(
        [PlannedStep(skill="move_item", arguments={"item_id": {"from": "selection", "item": 0}})],
        registry,
    )
    self_built = classify_steps([PlannedStep(skill="compress_to_zip")], registry)
    neither = classify_steps([PlannedStep(skill="list_items")], registry)

    assert has_selection_reference(explicit, registry) is True
    assert has_selection_reference(self_built, registry) is True
    assert has_selection_reference(neither, registry) is False


# --- resolve_arguments: unified + legacy step refs ------------------------


def test_resolve_arguments_handles_unified_and_legacy_step_refs() -> None:
    source = {0: StepResult(index=0, skill="search", ok=True, output={"items": [{"id": "X"}]})}

    unified = resolve_arguments({"parent_id": {"from": 0, "path": "items.0.id"}}, source)
    legacy = resolve_arguments({"parent_id": {"from_step": 0, "path": "items.0.id"}}, source)

    assert unified["parent_id"] == "X"
    assert legacy["parent_id"] == "X"


# --- validate_plan: selection refs accepted, bad step refs rejected -------


def test_validate_plan_accepts_selection_reference() -> None:
    registry = _registry()
    steps = [
        PlannedStep(skill="search", arguments={"q": "t"}),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": "selection", "each": True},
                "parent_id": {"from": 0, "path": "items.0.id"},
            },
            depends_on=[0],
        ),
    ]
    assert validate_plan(steps, registry) == []


def test_validate_plan_selection_ref_satisfies_required_arg() -> None:
    registry = _registry()
    # move_item requires item_id; a selection reference counts as supplied
    steps = [
        PlannedStep(skill="move_item", arguments={"item_id": {"from": "selection", "item": 0}}),
    ]
    assert validate_plan(steps, registry) == []


def test_validate_plan_still_rejects_forward_step_reference() -> None:
    registry = _registry()
    steps = [
        PlannedStep(
            skill="move_item",
            arguments={"item_id": "x", "parent_id": {"from": 3, "path": "items.0.id"}},
        ),
    ]
    problems = validate_plan(steps, registry)
    assert any("earlier step" in p for p in problems)
