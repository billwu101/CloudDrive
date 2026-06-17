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
from app.trash.service import TrashService


def _registry_with_writes(
    drive_service: DriveService, trash_service: TrashService | None = None
) -> SkillRegistry:
    registry = SkillRegistry()
    register_write_skills(registry, drive_service=drive_service, trash_service=trash_service)
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


async def test_rename_move_star_dispatch_to_drive_service() -> None:
    user_id = uuid4()
    item_id = uuid4()
    parent_id = uuid4()
    drive = AsyncMock(spec=DriveService)
    drive.rename.return_value = {"id": str(item_id), "name": "new"}
    drive.move.return_value = {"id": str(item_id)}
    drive.set_starred.return_value = {"id": str(item_id), "is_starred": True}
    registry = _registry_with_writes(drive)
    context = SkillContext(user_id=user_id)

    await registry.execute(
        name="rename_item",
        context=context,
        arguments={"item_id": str(item_id), "new_name": "new"},
    )
    drive.rename.assert_awaited_once_with(user_id, item_id, "new")

    await registry.execute(
        name="move_item",
        context=context,
        arguments={"item_id": str(item_id), "parent_id": str(parent_id)},
    )
    drive.move.assert_awaited_once_with(user_id, item_id, parent_id)

    await registry.execute(
        name="star_item",
        context=context,
        arguments={"item_id": str(item_id), "starred": True},
    )
    drive.set_starred.assert_awaited_once_with(user_id, item_id, True)


async def test_trash_and_restore_dispatch_to_trash_service() -> None:
    user_id = uuid4()
    item_id = uuid4()
    drive = AsyncMock(spec=DriveService)
    trash = AsyncMock(spec=TrashService)
    trash.trash_item.return_value = {"id": str(item_id), "is_deleted": True}
    trash.restore.return_value = {"id": str(item_id), "is_deleted": False}
    registry = _registry_with_writes(drive, trash)
    context = SkillContext(user_id=user_id)

    await registry.execute(name="trash_item", context=context, arguments={"item_id": str(item_id)})
    trash.trash_item.assert_awaited_once_with(user_id, item_id)

    await registry.execute(
        name="restore_item", context=context, arguments={"item_id": str(item_id)}
    )
    trash.restore.assert_awaited_once_with(user_id, item_id)


def test_trash_skills_absent_without_trash_service() -> None:
    drive = AsyncMock(spec=DriveService)
    registry = _registry_with_writes(drive)  # no trash_service
    names = {skill.name for skill in registry.list_skills()}
    assert "trash_item" not in names
    assert {"create_folder", "rename_item", "move_item", "star_item"} <= names


def test_write_and_destructive_tiers_all_require_confirmation() -> None:
    drive = AsyncMock(spec=DriveService)
    trash = AsyncMock(spec=TrashService)
    registry = _registry_with_writes(drive, trash)

    item = str(uuid4())
    steps = classify_steps(
        [
            PlannedStep(skill="rename_item", arguments={"item_id": item, "new_name": "n"}),
            PlannedStep(skill="trash_item", arguments={"item_id": item}),
        ],
        registry,
    )
    assert steps[0].permission_tier == "write"
    assert steps[1].permission_tier == "destructive"
    assert all(step.requires_approval for step in steps)
    assert is_auto_confirmable(steps) is False


async def test_invalid_uuid_argument_is_rejected() -> None:
    drive = AsyncMock(spec=DriveService)
    registry = _registry_with_writes(drive)

    with pytest.raises(AppError, match="Invalid UUID"):
        await registry.execute(
            name="rename_item",
            context=SkillContext(user_id=uuid4()),
            arguments={"item_id": "not-a-uuid", "new_name": "n"},
        )
    drive.rename.assert_not_awaited()
