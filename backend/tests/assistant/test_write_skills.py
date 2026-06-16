from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.assistant.permissions import classify_steps
from app.assistant.skills.builtin import register_write_skills
from app.assistant.skills.registry import SkillContext, SkillRegistry
from app.assistant.workflow import PlannedStep, is_auto_confirmable
from app.core.exceptions import AppError
from app.drive.service import DriveService


def _registry_with_writes(drive_service: DriveService) -> SkillRegistry:
    registry = SkillRegistry()
    register_write_skills(registry, drive_service=drive_service)
    return registry


async def test_create_folder_skill_calls_drive_service() -> None:
    user_id = uuid4()
    drive = AsyncMock(spec=DriveService)
    drive.create_folder.return_value = {
        "id": str(uuid4()),
        "name": "Reports",
        "item_type": "FOLDER",
    }
    registry = _registry_with_writes(drive)

    output = await registry.execute(
        name="create_folder",
        context=SkillContext(user_id=user_id),
        arguments={"name": "Reports"},
    )

    drive.create_folder.assert_awaited_once_with(user_id, None, "Reports")
    assert output["name"] == "Reports"


async def test_create_folder_requires_a_name() -> None:
    drive = AsyncMock(spec=DriveService)
    registry = _registry_with_writes(drive)

    with pytest.raises(AppError, match="Missing required argument"):
        await registry.execute(
            name="create_folder",
            context=SkillContext(user_id=uuid4()),
            arguments={},
        )
    drive.create_folder.assert_not_awaited()


def test_create_folder_is_write_tier_and_needs_confirmation() -> None:
    drive = AsyncMock(spec=DriveService)
    registry = _registry_with_writes(drive)

    steps = classify_steps([PlannedStep(skill="create_folder", arguments={"name": "X"})], registry)

    assert steps[0].permission_tier == "write"
    assert steps[0].requires_approval is True
    assert is_auto_confirmable(steps) is False
