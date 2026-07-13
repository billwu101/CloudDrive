from __future__ import annotations

from uuid import uuid4

from app.assistant.permissions import classify_steps
from app.assistant.skills.registry import RegisteredSkill, SkillRegistry
from app.assistant.workflow import (
    PlannedStep,
    expand_selection_steps,
    requires_file_selection,
)


async def _noop(ctx: object, args: object) -> None:
    return None


def _registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(
        RegisteredSkill(
            name="list_items",
            description="read",
            parameters={},
            permission_tier="read",
            handler=_noop,
        )
    )
    registry.register(
        RegisteredSkill(
            name="compress_to_zip",
            description="self-built",
            parameters={},
            permission_tier="write",
            handler=_noop,
            requires_selection=True,
        )
    )
    return registry


def test_requires_file_selection_detects_self_built_skill() -> None:
    registry = _registry()
    steps = classify_steps([PlannedStep(skill="compress_to_zip")], registry)
    assert requires_file_selection(steps, registry) is True

    read_steps = classify_steps([PlannedStep(skill="list_items")], registry)
    assert requires_file_selection(read_steps, registry) is False


def test_expand_runs_self_built_skill_once_per_selected_file() -> None:
    registry = _registry()
    steps = classify_steps([PlannedStep(skill="compress_to_zip")], registry)
    files = [uuid4(), uuid4(), uuid4()]

    expanded = expand_selection_steps(steps, files, registry)

    assert len(expanded) == 3  # one step per selected file
    assert [s.index for s in expanded] == [0, 1, 2]
    assert [s.arguments["item_id"] for s in expanded] == [str(f) for f in files]
    assert all(s.requires_approval for s in expanded)  # write tier → confirm


def test_expand_preserves_other_steps_and_remaps_dependencies() -> None:
    registry = _registry()
    # step 0: read; step 1: self-built (expands); step 2: read depends on step 0
    planned = [
        PlannedStep(skill="list_items"),
        PlannedStep(skill="compress_to_zip"),
        PlannedStep(skill="list_items", depends_on=[0]),
    ]
    steps = classify_steps(planned, registry)
    files = [uuid4(), uuid4()]

    expanded = expand_selection_steps(steps, files, registry)

    # 1 (read) + 2 (expanded) + 1 (read) = 4 steps, re-indexed 0..3
    assert [s.index for s in expanded] == [0, 1, 2, 3]
    # the trailing read step still depends on the first read step (new index 0)
    assert expanded[-1].depends_on == [0]
