"""find_folder: resolve a folder NAME to exactly one item, or say why not.

The failures these tests pin down were observed on real runs, both born of the
same gap — the planner could only express "the folder called X" as a fuzzy
``search`` plus a positional ``items.0.id``:

* the first result was a FILE → execution died on "Destination must be a folder";
* the search returned nothing → execution died on
  ``argument 'parent_id': cannot resolve path 'items.0.id' from step 0``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.assistant.skills.builtin import build_read_only_registry
from app.assistant.skills.registry import SkillContext, SkillOutput, SkillRegistry
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.service import DriveService
from app.search.service import SearchService
from app.trash.service import TrashService
from app.users.service import QuotaService


def _item(name: str, item_type: str = "FOLDER", **extra: Any) -> dict[str, Any]:
    return {"id": str(uuid4()), "name": name, "item_type": item_type, **extra}


def _page(items: list[dict[str, Any]], total: int | None = None) -> dict[str, Any]:
    return {
        "items": items,
        "total": len(items) if total is None else total,
        "page": 1,
        "page_size": 200,
        "pages": 1,
    }


def _registry(search: SearchService) -> SkillRegistry:
    return build_read_only_registry(
        drive_service=AsyncMock(spec=DriveService),
        search_service=search,
        quota_service=AsyncMock(spec=QuotaService),
        trash_service=AsyncMock(spec=TrashService),
    )


async def _find(search_result: dict[str, Any], name: str = "報告") -> Any:
    search = AsyncMock(spec=SearchService)
    search.search.return_value = search_result
    return await _registry(search).execute(
        name="find_folder",
        context=SkillContext(user_id=uuid4()),
        arguments={"name": name},
    )


async def test_unique_match_returns_one_item_referenceable_as_items_0_id() -> None:
    folder = _item("報告")

    output = await _find(_page([folder]))

    assert output == {"items": [folder], "total": 1}
    assert output["items"][0]["id"] == folder["id"]  # what "items.0.id" resolves to


async def test_declared_shape_is_paged_items_so_items_0_id_validates() -> None:
    """The declared output shape is what ``validate_plan`` checks references
    against; declaring anything else would have the planner corrected towards a
    path that does not resolve."""

    skill = _registry(AsyncMock(spec=SearchService)).get("find_folder")

    assert skill is not None
    assert skill.output is SkillOutput.PAGED_ITEMS
    assert skill.permission_tier == "read"  # read-only: no confirmation gate


async def test_search_is_asked_for_folders_at_the_largest_page() -> None:
    search = AsyncMock(spec=SearchService)
    search.search.return_value = _page([_item("報告")])
    user_id = uuid4()

    await _registry(search).execute(
        name="find_folder",
        context=SkillContext(user_id=user_id),
        arguments={"name": "報告"},
    )

    args, kwargs = search.search.call_args
    assert args[0] == user_id
    assert args[1] == "報告"
    assert kwargs["item_type"] == "FOLDER"
    assert kwargs["page_size"] == 200  # a match on row 21 must not read as "not found"


async def test_case_differences_still_count_as_the_same_name() -> None:
    folder = _item("Reports")

    output = await _find(_page([folder]), name="reports")

    assert output["items"] == [folder]


async def test_a_substring_match_is_not_a_match() -> None:
    """The whole point: ``search`` is a substring match, this skill is not."""

    with pytest.raises(AppError) as excinfo:
        await _find(_page([_item("報告2025"), _item("舊報告")]))

    assert excinfo.value.code is ErrorCode.NOT_FOUND


async def test_no_match_fails_with_a_sentence_the_user_can_read() -> None:
    """A step that returned an empty page instead would only move the failure
    downstream, where ``items.0.id`` dies with "cannot resolve path"."""

    with pytest.raises(AppError) as excinfo:
        await _find(_page([]))

    message = excinfo.value.message
    assert "找不到名為「報告」的資料夾" in message
    assert "cannot resolve" not in message
    assert "items.0" not in message


async def test_no_exact_match_names_the_near_misses() -> None:
    with pytest.raises(AppError) as excinfo:
        await _find(_page([_item("報告2025"), _item("年度報告")]))

    assert "報告2025" in excinfo.value.message
    assert "年度報告" in excinfo.value.message


async def test_several_folders_with_the_same_name_are_all_reported() -> None:
    """Never pick one. ORDER BY name makes "the first" alphabetical, not best —
    exactly the blind items.0 this skill replaces."""

    matches = [
        _item("報告", updated_at="2026-01-05T10:00:00Z"),
        _item("報告", updated_at="2026-07-30T09:00:00Z"),
    ]

    with pytest.raises(AppError) as excinfo:
        await _find(_page(matches))

    message = excinfo.value.message
    assert "2 個資料夾都叫「報告」" in message
    assert "2026-01-05" in message and "2026-07-30" in message
    assert "請告訴我要用哪一個" in message
    assert excinfo.value.code is ErrorCode.INVALID_OPERATION


async def test_more_candidates_than_one_page_is_reported_not_truncated() -> None:
    """Measured on the real database: 266 folders matched one name. Answering
    from the first 200 would be answering from a truncated list."""

    with pytest.raises(AppError) as excinfo:
        await _find(_page([_item("報告") for _ in range(200)], total=266))

    assert "266 個" in excinfo.value.message
    assert "更完整的名稱" in excinfo.value.message


async def test_a_file_with_the_identical_name_is_never_returned() -> None:
    """search is already asked for FOLDER only; this is the second lock. A file
    reaching a parent_id argument is the "Destination must be a folder" run."""

    with pytest.raises(AppError) as excinfo:
        await _find(_page([_item("報告", item_type="FILE")]))

    assert excinfo.value.code is ErrorCode.NOT_FOUND


async def test_a_file_alongside_the_folder_leaves_only_the_folder() -> None:
    folder = _item("報告")

    output = await _find(_page([_item("報告", item_type="FILE"), folder]))

    assert output == {"items": [folder], "total": 1}


async def test_missing_name_argument_is_rejected() -> None:
    with pytest.raises(AppError) as excinfo:
        await _find(_page([]), name="   ")

    assert excinfo.value.code is ErrorCode.INVALID_OPERATION
    assert "name" in excinfo.value.message


async def test_search_skill_still_returns_whatever_search_gives_it() -> None:
    """Regression: find_folder must not have changed how ``search`` behaves."""

    page = _page([_item("報告2025"), _item("報告.txt", item_type="FILE")])
    search = AsyncMock(spec=SearchService)
    search.search.return_value = page

    output = await _registry(search).execute(
        name="search",
        context=SkillContext(user_id=uuid4()),
        arguments={"q": "報告"},
    )

    assert output == page
