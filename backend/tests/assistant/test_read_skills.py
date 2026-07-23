from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import uuid4

from app.assistant.skills.builtin import build_read_only_registry
from app.assistant.skills.registry import SkillContext, SkillRegistry
from app.drive.service import DriveService
from app.search.service import SearchService
from app.trash.service import TrashService
from app.users.service import QuotaService


def _read_registry(trash: TrashService) -> SkillRegistry:
    return build_read_only_registry(
        drive_service=AsyncMock(spec=DriveService),
        search_service=AsyncMock(spec=SearchService),
        quota_service=AsyncMock(spec=QuotaService),
        trash_service=trash,
    )


async def test_list_trash_skill_is_registered_and_calls_service() -> None:
    user_id = uuid4()
    trash = AsyncMock(spec=TrashService)
    trash.list_trash.return_value = {"items": [{"id": "a"}], "total": 1}
    registry = _read_registry(trash)

    assert registry.get("list_trash") is not None  # exposed to the planner

    output = await registry.execute(
        name="list_trash",
        context=SkillContext(user_id=user_id),
        arguments={},
    )

    trash.list_trash.assert_awaited_once_with(user_id, page=1, page_size=50)
    assert output == {"items": [{"id": "a"}], "total": 1}
