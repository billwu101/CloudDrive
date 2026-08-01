from __future__ import annotations

from collections.abc import Mapping
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
    WorkflowExecutor,
    apply_selection,
    has_fanout,
    has_selection_reference,
    is_selection_ref,
    is_step_ref,
    resolve_arguments,
    resolve_fanout_arguments,
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


def test_resolve_arguments_rejects_file_destination_with_name() -> None:
    source = {
        0: StepResult(
            index=0,
            skill="search",
            ok=True,
            output={"items": [{"id": "FILE-ID", "name": "budget.xlsx", "item_type": "FILE"}]},
        )
    }

    with pytest.raises(StepResolutionError, match=r"budget.xlsx.*檔案"):
        resolve_arguments({"parent_id": {"from": 0, "path": "items.0.id"}}, source)


def test_resolve_arguments_allows_folder_destination() -> None:
    source = {
        0: StepResult(
            index=0,
            skill="search",
            ok=True,
            output={"items": [{"id": "FOLDER-ID", "name": "Archive", "item_type": "FOLDER"}]},
        )
    }

    resolved = resolve_arguments({"parent_id": {"from": 0, "path": "items.0.id"}}, source)

    assert resolved["parent_id"] == "FOLDER-ID"


def test_resolve_arguments_allows_destination_with_unknown_type() -> None:
    source = {
        0: StepResult(
            index=0,
            skill="custom_lookup",
            ok=True,
            output={"items": [{"id": "OPAQUE-ID", "name": "opaque result"}]},
        )
    }

    resolved = resolve_arguments({"parent_id": {"from": 0, "path": "items.0.id"}}, source)

    assert resolved["parent_id"] == "OPAQUE-ID"


def test_resolve_arguments_does_not_type_check_non_destination_argument() -> None:
    source = {
        0: StepResult(
            index=0,
            skill="search",
            ok=True,
            output={"items": [{"id": "FILE-ID", "name": "budget.xlsx", "item_type": "FILE"}]},
        )
    }

    resolved = resolve_arguments({"item_id": {"from": 0, "path": "items.0.id"}}, source)

    assert resolved["item_id"] == "FILE-ID"


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


def test_validate_plan_accepts_wildcard_step_reference() -> None:
    registry = _registry()
    # "trash everything in a folder": list then trash each returned item
    steps = [
        PlannedStep(skill="list_items", arguments={"parent_id": "x"}),
        PlannedStep(
            skill="move_item",
            arguments={"item_id": {"from": 0, "path": "items.*.id"}, "parent_id": "y"},
            depends_on=[0],
        ),
    ]
    assert validate_plan(steps, registry) == []


# --- wildcard fan-out over a step's list output ---------------------------


def test_has_fanout_detects_wildcard_only() -> None:
    assert has_fanout({"item_id": {"from": 1, "path": "items.*.id"}}) is True
    assert has_fanout({"item_id": {"from": 1, "path": "items.0.id"}}) is False
    assert has_fanout({"item_id": "literal"}) is False


def test_resolve_fanout_expands_once_per_item_and_shares_other_args() -> None:
    src = {
        1: StepResult(
            index=1,
            skill="list_items",
            ok=True,
            output={"items": [{"id": "a"}, {"id": "b"}, {"id": "c"}]},
        ),
        0: StepResult(index=0, skill="search", ok=True, output={"items": [{"id": "DEST"}]}),
    }
    arg_sets = resolve_fanout_arguments(
        {
            "item_id": {"from": 1, "path": "items.*.id"},
            "parent_id": {"from": 0, "path": "items.0.id"},
        },
        src,
    )
    assert [a["item_id"] for a in arg_sets] == ["a", "b", "c"]  # one per listed item
    assert all(a["parent_id"] == "DEST" for a in arg_sets)  # shared destination


def test_resolve_fanout_empty_list_yields_no_calls() -> None:
    src = {1: StepResult(index=1, skill="list_items", ok=True, output={"items": []})}
    assert resolve_fanout_arguments({"item_id": {"from": 1, "path": "items.*.id"}}, src) == []


def test_resolve_fanout_non_list_raises() -> None:
    src = {1: StepResult(index=1, skill="x", ok=True, output={"items": {"id": "a"}})}
    with pytest.raises(StepResolutionError):
        resolve_fanout_arguments({"item_id": {"from": 1, "path": "items.*.id"}}, src)


async def test_executor_runs_fanout_skill_once_per_item() -> None:
    trashed: list[str] = []
    registry = SkillRegistry()

    async def _list(ctx: object, args: Mapping[str, Any]) -> dict[str, Any]:
        return {"items": [{"id": "a"}, {"id": "b"}], "total": 2}

    async def _trash(ctx: object, args: Mapping[str, Any]) -> dict[str, Any]:
        trashed.append(str(args["item_id"]))
        return {"trashed": args["item_id"]}

    registry.register(
        RegisteredSkill(
            name="list_items", description="", parameters={}, permission_tier="read", handler=_list
        )
    )
    registry.register(
        RegisteredSkill(
            name="trash_item",
            description="",
            parameters={"type": "object", "required": ["item_id"]},
            permission_tier="destructive",
            handler=_trash,
        )
    )
    steps = classify_steps(
        [
            PlannedStep(skill="list_items", arguments={"parent_id": "f"}),
            PlannedStep(
                skill="trash_item",
                arguments={"item_id": {"from": 0, "path": "items.*.id"}},
                depends_on=[0],
            ),
        ],
        registry,
    )

    results = await WorkflowExecutor(registry=registry).execute(user_id=uuid4(), steps=steps)

    assert trashed == ["a", "b"]  # ran once per listed file
    assert results[1].ok is True
    assert results[1].output == {"items": [{"trashed": "a"}, {"trashed": "b"}], "count": 2}


async def test_executor_rejects_file_destination_before_write_executes() -> None:
    writes: list[Mapping[str, Any]] = []
    registry = SkillRegistry()

    async def _search(ctx: object, args: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "items": [{"id": "FILE-ID", "name": "annual-report.pdf", "item_type": "FILE"}],
            "total": 1,
        }

    async def _move(ctx: object, args: Mapping[str, Any]) -> None:
        writes.append(args)

    registry.register(
        RegisteredSkill(
            name="search", description="", parameters={}, permission_tier="read", handler=_search
        )
    )
    registry.register(
        RegisteredSkill(
            name="move_item", description="", parameters={}, permission_tier="write", handler=_move
        )
    )
    steps = classify_steps(
        [
            PlannedStep(skill="search"),
            PlannedStep(
                skill="move_item",
                arguments={"item_id": "SOURCE-ID", "parent_id": {"from": 0, "path": "items.0.id"}},
                depends_on=[0],
            ),
        ],
        registry,
    )

    results = await WorkflowExecutor(registry=registry).execute(user_id=uuid4(), steps=steps)

    assert writes == []
    assert results[1].ok is False
    assert "annual-report.pdf" in str(results[1].error)
    assert "檔案" in str(results[1].error)


async def test_fanout_validates_every_destination_before_any_write_executes() -> None:
    writes: list[Mapping[str, Any]] = []
    registry = SkillRegistry()

    async def _search(ctx: object, args: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "items": [
                {"id": "FOLDER-ID", "name": "Archive", "item_type": "FOLDER"},
                {"id": "FILE-ID", "name": "notes.txt", "item_type": "FILE"},
            ],
            "total": 2,
        }

    async def _move(ctx: object, args: Mapping[str, Any]) -> None:
        writes.append(args)

    registry.register(
        RegisteredSkill(
            name="search", description="", parameters={}, permission_tier="read", handler=_search
        )
    )
    registry.register(
        RegisteredSkill(
            name="move_item", description="", parameters={}, permission_tier="write", handler=_move
        )
    )
    steps = classify_steps(
        [
            PlannedStep(skill="search"),
            PlannedStep(
                skill="move_item",
                arguments={
                    "item_id": "SOURCE-ID",
                    "parent_id": {"from": 0, "path": "items.*.id"},
                },
                depends_on=[0],
            ),
        ],
        registry,
    )

    results = await WorkflowExecutor(registry=registry).execute(user_id=uuid4(), steps=steps)

    assert writes == []
    assert results[1].ok is False
    assert "notes.txt" in str(results[1].error)


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
