from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.permission.permissions import Permission
from app.search.repository import AbstractSearchRepository
from app.search.service import SearchService
from tests.drive.test_service import _item
from tests.permission.test_service import _share

# ── In-memory search repository ──────────────────────────────────────────────


class MemSearchRepo(AbstractSearchRepository):
    def __init__(
        self,
        items: list[DriveItem] | None = None,
        shares: list[Share] | None = None,
    ) -> None:
        self._items = items or []
        self._shares = shares or []

    async def search(
        self,
        user_id: UUID,
        query: str,
        *,
        item_type: str | None = None,
        mime_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DriveItem], int]:
        shared_ids = {s.item_id for s in self._shares if s.target_user_id == user_id}
        q = query.lower()
        matched = [
            i
            for i in self._items
            if not i.is_deleted
            and (i.owner_id == user_id or i.id in shared_ids)
            and q in i.name.lower()
        ]
        if item_type is not None:
            matched = [i for i in matched if i.item_type == item_type]
        if mime_type is not None:
            matched = [i for i in matched if i.mime_type == mime_type]
        total = len(matched)
        return matched[offset : offset + limit], total


def _svc(items: list[DriveItem] | None = None, shares: list[Share] | None = None) -> SearchService:
    return SearchService(repo=MemSearchRepo(items, shares))


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_search_own_files() -> None:
    user = uuid4()
    item = _item(owner_id=user, name="budget.xlsx")
    svc = _svc(items=[item])
    page = await svc.search(user, "budget")
    assert page.total == 1
    assert page.items[0].name == "budget.xlsx"


async def test_search_shared_files() -> None:
    owner = uuid4()
    user = uuid4()
    item = _item(owner_id=owner, name="shared_doc.txt")
    share = _share(item.id, user, Permission.VIEWER)
    svc = _svc(items=[item], shares=[share])
    page = await svc.search(user, "shared_doc")
    assert page.total == 1


async def test_search_does_not_return_unshared_files() -> None:
    owner = uuid4()
    user = uuid4()
    item = _item(owner_id=owner, name="private.txt")
    svc = _svc(items=[item])
    page = await svc.search(user, "private")
    assert page.total == 0


async def test_search_excludes_deleted_items() -> None:
    user = uuid4()
    deleted = _item(owner_id=user, name="gone.txt", is_deleted=True)
    svc = _svc(items=[deleted])
    page = await svc.search(user, "gone")
    assert page.total == 0


async def test_search_filter_by_file_type() -> None:
    user = uuid4()
    folder = _item(owner_id=user, name="budget", item_type=ItemType.FOLDER)
    file = _item(owner_id=user, name="budget", item_type=ItemType.FILE)
    svc = _svc(items=[folder, file])
    page = await svc.search(user, "budget", item_type=ItemType.FILE)
    assert page.total == 1
    assert page.items[0].item_type == ItemType.FILE


async def test_search_filter_by_folder_type() -> None:
    user = uuid4()
    folder = _item(owner_id=user, name="docs", item_type=ItemType.FOLDER)
    file = _item(owner_id=user, name="docs", item_type=ItemType.FILE)
    svc = _svc(items=[folder, file])
    page = await svc.search(user, "docs", item_type=ItemType.FOLDER)
    assert page.total == 1
    assert page.items[0].item_type == ItemType.FOLDER


async def test_search_filter_by_mime_type() -> None:
    user = uuid4()
    pdf = _item(owner_id=user, name="report", item_type=ItemType.FILE)
    pdf.mime_type = "application/pdf"
    txt = _item(owner_id=user, name="report", item_type=ItemType.FILE)
    txt.mime_type = "text/plain"
    svc = _svc(items=[pdf, txt])
    page = await svc.search(user, "report", mime_type="application/pdf")
    assert page.total == 1


async def test_search_pagination() -> None:
    user = uuid4()
    items = [_item(owner_id=user, name=f"file_{i}.txt") for i in range(10)]
    svc = _svc(items=items)
    page = await svc.search(user, "file", page=1, page_size=5)
    assert len(page.items) == 5
    assert page.total == 10


async def test_search_empty_query_raises() -> None:
    user = uuid4()
    svc = _svc()
    with pytest.raises(AppError) as exc_info:
        await svc.search(user, "   ")
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION
