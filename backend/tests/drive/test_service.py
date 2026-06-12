from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.drive.repository import (
    AbstractDriveItemRepository,
    AbstractUserItemPreferenceRepository,
)
from app.drive.schemas import DriveItemSortField, ItemType
from app.drive.service import DriveService
from app.models.drive_item import DriveItem
from app.models.user_item_preference import UserItemPreference
from app.schemas.common import SortOrder

# ── Fake repositories ────────────────────────────────────────────────────────


def _item(
    *,
    owner_id: UUID,
    parent_id: UUID | None = None,
    item_type: str = ItemType.FOLDER,
    name: str = "Untitled",
    is_deleted: bool = False,
) -> DriveItem:
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=parent_id,
        item_type=item_type,
        name=name,
        mime_type=None,
        extension=None,
        size_bytes=0,
        storage_key=None,
        checksum_sha256=None,
        is_starred=False,
        is_deleted=is_deleted,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


class MemDriveItemRepo(AbstractDriveItemRepository):
    def __init__(self, items: list[DriveItem] | None = None) -> None:
        self._items: dict[UUID, DriveItem] = {i.id: i for i in (items or [])}

    def _add(self, item: DriveItem) -> DriveItem:
        self._items[item.id] = item
        return item

    async def get_by_id(self, item_id: UUID) -> DriveItem | None:
        return self._items.get(item_id)

    async def list_children(
        self,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        sort_by: DriveItemSortField,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[DriveItem], int]:
        matched = [
            i
            for i in self._items.values()
            if i.owner_id == owner_id and i.parent_id == parent_id and not i.is_deleted
        ]
        total = len(matched)
        return matched[offset : offset + limit], total

    async def create(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID | None,
        item_type: str,
        name: str,
        created_by: UUID,
    ) -> DriveItem:
        item = _item(owner_id=owner_id, parent_id=parent_id, item_type=item_type, name=name)
        item.created_by = created_by
        return self._add(item)

    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem:
        item = self._items[item_id]
        item.name = name
        item.updated_by = updated_by
        return item

    async def update_parent(
        self, item_id: UUID, parent_id: UUID | None, updated_by: UUID
    ) -> DriveItem:
        item = self._items[item_id]
        item.parent_id = parent_id
        item.updated_by = updated_by
        return item

    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        return any(
            i
            for i in self._items.values()
            if i.owner_id == owner_id
            and i.parent_id == parent_id
            and i.name == name
            and not i.is_deleted
            and i.id != exclude_id
        )


class MemPrefRepo(AbstractUserItemPreferenceRepository):
    def __init__(self) -> None:
        self._prefs: dict[tuple[UUID, UUID], UserItemPreference] = {}

    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None:
        return self._prefs.get((user_id, item_id))

    async def upsert_preference(
        self, user_id: UUID, item_id: UUID, *, is_starred: bool
    ) -> UserItemPreference:
        now = datetime.now(UTC)
        key = (user_id, item_id)
        pref = self._prefs.get(key)
        if pref is None:
            pref = UserItemPreference(
                id=uuid4(),
                user_id=user_id,
                item_id=item_id,
                is_starred=is_starred,
                created_at=now,
                updated_at=now,
            )
            self._prefs[key] = pref
        else:
            pref.is_starred = is_starred
            pref.updated_at = now
        return pref

    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]:
        return {
            iid for iid in item_ids if (pref := self._prefs.get((user_id, iid))) and pref.is_starred
        }


def _svc(items: list[DriveItem] | None = None) -> DriveService:
    return DriveService(
        item_repo=MemDriveItemRepo(items),
        pref_repo=MemPrefRepo(),
    )


# ── create_folder ────────────────────────────────────────────────────────────


class TestCreateFolder:
    async def test_create_root_folder(self) -> None:
        user = uuid4()
        svc = _svc()
        resp = await svc.create_folder(user, None, "Documents")
        assert resp.name == "Documents"
        assert resp.parent_id is None
        assert resp.item_type == ItemType.FOLDER
        assert resp.is_starred is False

    async def test_create_subfolder(self) -> None:
        user = uuid4()
        parent = _item(owner_id=user, name="Root")
        svc = _svc([parent])
        resp = await svc.create_folder(user, parent.id, "Sub")
        assert resp.parent_id == parent.id

    async def test_name_conflict_raises(self) -> None:
        user = uuid4()
        existing = _item(owner_id=user, name="Docs")
        svc = _svc([existing])
        with pytest.raises(AppError) as exc_info:
            await svc.create_folder(user, None, "Docs")
        assert exc_info.value.code == ErrorCode.NAME_CONFLICT

    async def test_different_parents_can_share_name(self) -> None:
        user = uuid4()
        parent = _item(owner_id=user, name="Root")
        existing = _item(owner_id=user, parent_id=parent.id, name="Docs")
        svc = _svc([parent, existing])
        resp = await svc.create_folder(user, None, "Docs")
        assert resp.name == "Docs"

    async def test_parent_not_found_raises(self) -> None:
        svc = _svc()
        with pytest.raises(NotFoundError):
            await svc.create_folder(uuid4(), uuid4(), "Oops")

    async def test_invalid_name_slash_raises(self) -> None:
        svc = _svc()
        with pytest.raises(AppError):
            await svc.create_folder(uuid4(), None, "bad/name")

    async def test_empty_name_raises(self) -> None:
        svc = _svc()
        with pytest.raises(AppError):
            await svc.create_folder(uuid4(), None, "   ")


# ── rename ───────────────────────────────────────────────────────────────────


class TestRename:
    async def test_rename_success(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="old")
        svc = _svc([item])
        resp = await svc.rename(user, item.id, "new")
        assert resp.name == "new"

    async def test_rename_conflict_raises(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="a")
        other = _item(owner_id=user, name="b")
        svc = _svc([item, other])
        with pytest.raises(AppError) as exc_info:
            await svc.rename(user, item.id, "b")
        assert exc_info.value.code == ErrorCode.NAME_CONFLICT

    async def test_rename_other_user_raises(self) -> None:
        owner = uuid4()
        other = uuid4()
        item = _item(owner_id=owner, name="mine")
        svc = _svc([item])
        with pytest.raises(ForbiddenError):
            await svc.rename(other, item.id, "stolen")

    async def test_rename_not_found_raises(self) -> None:
        svc = _svc()
        with pytest.raises(NotFoundError):
            await svc.rename(uuid4(), uuid4(), "x")


# ── move ─────────────────────────────────────────────────────────────────────


class TestMove:
    async def test_move_to_different_folder(self) -> None:
        user = uuid4()
        src = _item(owner_id=user, name="file")
        dest = _item(owner_id=user, name="Dest")
        svc = _svc([src, dest])
        resp = await svc.move(user, src.id, dest.id)
        assert resp.parent_id == dest.id

    async def test_move_to_root(self) -> None:
        user = uuid4()
        parent = _item(owner_id=user, name="Parent")
        item = _item(owner_id=user, parent_id=parent.id, name="file")
        svc = _svc([parent, item])
        resp = await svc.move(user, item.id, None)
        assert resp.parent_id is None

    async def test_move_to_nonexistent_raises(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="file")
        svc = _svc([item])
        with pytest.raises(NotFoundError):
            await svc.move(user, item.id, uuid4())

    async def test_move_folder_into_itself_raises(self) -> None:
        user = uuid4()
        folder = _item(owner_id=user, name="folder")
        svc = _svc([folder])
        with pytest.raises(AppError) as exc_info:
            await svc.move(user, folder.id, folder.id)
        assert exc_info.value.code == ErrorCode.INVALID_OPERATION

    async def test_move_folder_into_child_raises(self) -> None:
        user = uuid4()
        parent = _item(owner_id=user, name="parent")
        child = _item(owner_id=user, parent_id=parent.id, name="child")
        svc = _svc([parent, child])
        with pytest.raises(AppError) as exc_info:
            await svc.move(user, parent.id, child.id)
        assert exc_info.value.code == ErrorCode.INVALID_OPERATION

    async def test_move_other_user_item_raises(self) -> None:
        owner = uuid4()
        other = uuid4()
        item = _item(owner_id=owner, name="mine")
        svc = _svc([item])
        with pytest.raises(ForbiddenError):
            await svc.move(other, item.id, None)


# ── set_starred ───────────────────────────────────────────────────────────────


class TestSetStarred:
    async def test_star_item(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="report.pdf", item_type=ItemType.FILE)
        svc = _svc([item])
        resp = await svc.set_starred(user, item.id, is_starred=True)
        assert resp.is_starred is True

    async def test_unstar_item(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="report.pdf", item_type=ItemType.FILE)
        svc = _svc([item])
        await svc.set_starred(user, item.id, is_starred=True)
        resp = await svc.set_starred(user, item.id, is_starred=False)
        assert resp.is_starred is False

    async def test_is_starred_per_user(self) -> None:
        user1, user2 = uuid4(), uuid4()
        item1 = _item(owner_id=user1, name="shared")
        item2 = _item(owner_id=user2, name="shared")
        svc1 = _svc([item1])
        svc2 = _svc([item2])
        await svc1.set_starred(user1, item1.id, is_starred=True)
        resp2 = await svc2.get_item(user2, item2.id)
        assert resp2.is_starred is False


# ── list_items ────────────────────────────────────────────────────────────────


class TestListItems:
    async def test_list_root_items(self) -> None:
        user = uuid4()
        f1 = _item(owner_id=user, name="A")
        f2 = _item(owner_id=user, name="B")
        svc = _svc([f1, f2])
        page = await svc.list_items(user, None)
        assert page.total == 2
        assert page.page == 1

    async def test_pagination(self) -> None:
        user = uuid4()
        items = [_item(owner_id=user, name=str(i)) for i in range(5)]
        svc = _svc(items)
        page = await svc.list_items(user, None, page=1, page_size=2)
        assert page.page_size == 2
        assert page.total == 5
        assert len(page.items) == 2
        assert page.pages == 3

    async def test_parent_not_owned_raises(self) -> None:
        owner = uuid4()
        other = uuid4()
        folder = _item(owner_id=owner, name="Folder")
        svc = _svc([folder])
        with pytest.raises(ForbiddenError):
            await svc.list_items(other, folder.id)

    async def test_deleted_parent_raises(self) -> None:
        user = uuid4()
        folder = _item(owner_id=user, name="Folder", is_deleted=True)
        svc = _svc([folder])
        with pytest.raises(NotFoundError):
            await svc.list_items(user, folder.id)


# ── edge cases ────────────────────────────────────────────────────────────────


class TestValidateName:
    async def test_name_too_long_raises(self) -> None:
        svc = _svc()
        long_name = "a" * 513
        with pytest.raises(AppError):
            await svc.create_folder(uuid4(), None, long_name)


class TestCreateFolderEdgeCases:
    async def test_parent_is_file_raises(self) -> None:
        user = uuid4()
        file_item = _item(owner_id=user, name="file.txt", item_type=ItemType.FILE)
        svc = _svc([file_item])
        with pytest.raises(AppError) as exc_info:
            await svc.create_folder(user, file_item.id, "Sub")
        assert exc_info.value.code == ErrorCode.INVALID_OPERATION


class TestRenameEdgeCases:
    async def test_rename_same_name_noop(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="same")
        svc = _svc([item])
        resp = await svc.rename(user, item.id, "same")
        assert resp.name == "same"


class TestMoveEdgeCases:
    async def test_move_dest_not_owned_raises(self) -> None:
        owner = uuid4()
        other = uuid4()
        item = _item(owner_id=owner, name="item")
        dest = _item(owner_id=other, name="dest")
        svc = _svc([item, dest])
        with pytest.raises(ForbiddenError):
            await svc.move(owner, item.id, dest.id)

    async def test_move_dest_is_file_raises(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="item")
        file_dest = _item(owner_id=user, name="dest.txt", item_type=ItemType.FILE)
        svc = _svc([item, file_dest])
        with pytest.raises(AppError) as exc_info:
            await svc.move(user, item.id, file_dest.id)
        assert exc_info.value.code == ErrorCode.INVALID_OPERATION

    async def test_move_name_conflict_in_dest_raises(self) -> None:
        user = uuid4()
        item = _item(owner_id=user, name="docs")
        dest = _item(owner_id=user, name="dest")
        conflict = _item(owner_id=user, parent_id=dest.id, name="docs")
        svc = _svc([item, dest, conflict])
        with pytest.raises(AppError) as exc_info:
            await svc.move(user, item.id, dest.id)
        assert exc_info.value.code == ErrorCode.NAME_CONFLICT


class TestGetRecent:
    async def test_get_recent_with_activity(self) -> None:
        from unittest.mock import AsyncMock

        from app.activity_log.service import ActivityLogService

        user = uuid4()
        item1 = _item(owner_id=user, name="recent1")
        item2 = _item(owner_id=user, name="recent2")
        activity_svc = AsyncMock(spec=ActivityLogService)
        activity_svc.get_recent_item_ids.return_value = [item2.id, item1.id]
        svc = DriveService(
            item_repo=MemDriveItemRepo([item1, item2]),
            pref_repo=MemPrefRepo(),
            activity_svc=activity_svc,
        )
        results = await svc.get_recent(user)
        assert len(results) == 2
        assert results[0].name == "recent2"

    async def test_get_recent_skips_deleted(self) -> None:
        from unittest.mock import AsyncMock

        from app.activity_log.service import ActivityLogService

        user = uuid4()
        alive = _item(owner_id=user, name="alive")
        dead = _item(owner_id=user, name="dead", is_deleted=True)
        activity_svc = AsyncMock(spec=ActivityLogService)
        activity_svc.get_recent_item_ids.return_value = [dead.id, alive.id]
        svc = DriveService(
            item_repo=MemDriveItemRepo([alive, dead]),
            pref_repo=MemPrefRepo(),
            activity_svc=activity_svc,
        )
        results = await svc.get_recent(user)
        assert len(results) == 1
        assert results[0].name == "alive"

    async def test_get_recent_no_activity_service_returns_empty(self) -> None:
        user = uuid4()
        svc = _svc()
        results = await svc.get_recent(user)
        assert results == []
