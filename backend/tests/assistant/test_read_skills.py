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


def test_search_description_admits_it_matches_content_and_orders_by_name() -> None:
    """It used to say "by name", which is only half of what the repository does
    (`app/search/repository.py`: name ILIKE, indexed content ILIKE, and the
    English tsvector) — a description the model can only act on wrongly, since
    it also orders by name and so hands back an alphabetical first hit."""

    skill = _read_registry(AsyncMock(spec=TrashService)).get("search")

    assert skill is not None
    assert "content of files" in skill.description
    assert "find_folder" in skill.description  # points at the exact-name lookup


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

    trash.list_trash.assert_awaited_once_with(user_id, page=1, page_size=50, name=None)
    assert output == {"items": [{"id": "a"}], "total": 1}


async def test_list_trash_skill_passes_name_filter() -> None:
    trash = AsyncMock(spec=TrashService)
    trash.list_trash.return_value = {"items": [], "total": 0}
    registry = _read_registry(trash)

    await registry.execute(
        name="list_trash",
        context=SkillContext(user_id=uuid4()),
        arguments={"q": "test3"},
    )

    _, kwargs = trash.list_trash.call_args
    assert kwargs["name"] == "test3"  # q → name filter
