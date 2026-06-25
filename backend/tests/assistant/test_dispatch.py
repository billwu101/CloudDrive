from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import uuid4

import pytest

from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.core.exceptions import AppError


async def test_registry_dispatches_registered_skill_with_user_context() -> None:
    user_id = uuid4()
    registry = SkillRegistry()

    async def handler(context: SkillContext, args: Mapping[str, Any]) -> dict[str, Any]:
        return {"user_id": str(context.user_id), "args": dict(args)}

    registry.register(
        RegisteredSkill(
            name="echo",
            description="Echo arguments.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=handler,
        )
    )

    result = await registry.execute(
        name="echo",
        context=SkillContext(user_id=user_id),
        arguments={"q": "hello"},
    )

    assert result == {"user_id": str(user_id), "args": {"q": "hello"}}


async def test_registry_rejects_unknown_skill() -> None:
    registry = SkillRegistry()

    with pytest.raises(AppError, match="Unknown assistant skill"):
        await registry.execute(
            name="missing",
            context=SkillContext(user_id=uuid4()),
            arguments={},
        )
