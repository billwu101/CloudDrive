from __future__ import annotations

import pytest

from app.assistant.permissions import classify_steps
from app.assistant.skills.registry import RegisteredSkill, SkillRegistry
from app.assistant.workflow import PlannedStep, is_auto_confirmable
from app.core.exceptions import AppError


def _registry() -> SkillRegistry:
    registry = SkillRegistry()

    async def handler(context, args):  # type: ignore[no-untyped-def]
        return {}

    for name, tier in (("list_items", "read"), ("delete_item", "destructive")):
        registry.register(
            RegisteredSkill(
                name=name,
                description=name,
                parameters={"type": "object", "properties": {}, "additionalProperties": True},
                permission_tier=tier,
                handler=handler,
            )
        )
    return registry


def test_read_only_steps_are_auto_confirmable() -> None:
    steps = classify_steps([PlannedStep(skill="list_items")], _registry())
    assert steps[0].permission_tier == "read"
    assert steps[0].requires_approval is False
    assert is_auto_confirmable(steps) is True


def test_destructive_step_requires_approval() -> None:
    steps = classify_steps(
        [PlannedStep(skill="list_items"), PlannedStep(skill="delete_item")],
        _registry(),
    )
    assert steps[1].requires_approval is True
    assert is_auto_confirmable(steps) is False


def test_unknown_skill_is_rejected() -> None:
    with pytest.raises(AppError, match="unknown skill"):
        classify_steps([PlannedStep(skill="rm_rf")], _registry())


def test_forward_dependency_is_rejected() -> None:
    with pytest.raises(AppError, match="invalid dependency"):
        classify_steps([PlannedStep(skill="list_items", depends_on=[1])], _registry())
