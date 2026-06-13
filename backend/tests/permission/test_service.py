from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ForbiddenError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import DriveItemSortField, ItemType
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.permission.permissions import Permission
from app.permission.repository import AbstractShareRepository
from app.permission.service import PermissionService
from app.schemas.common import SortOrder

# ── Fake repositories ────────────────────────────────────────────────────────


def _item(
    *,
    owner_id: UUID,
    parent_id: UUID | None = None,
    item_type: str = ItemType.FOLDER,
) -> DriveItem:
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=parent_id,
        item_type=item_type,
        name="item",
        mime_type=None,
        extension=None,
        size_bytes=0,
        storage_key=None,
        checksum_sha256=None,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def _share(item_id: UUID, target_user_id: UUID, permission: Permission) -> Share:
    now = datetime.now(UTC)
    return Share(
        id=uuid4(),
        item_id=item_id,
        owner_id=uuid4(),
        target_user_id=target_user_id,
        permission=permission.value,
        created_at=now,
        updated_at=now,
    )


class MemShareRepo(AbstractShareRepository):
    def __init__(self, shares: list[Share] | None = None) -> None:
        self._shares: list[Share] = shares or []

    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None:
        return next(
            (s for s in self._shares if s.item_id == item_id and s.target_user_id == user_id),
            None,
        )

    async def delete_by_item(self, item_id: UUID) -> None:
        self._shares = [s for s in self._shares if s.item_id != item_id]


class MemItemRepo(AbstractDriveItemRepository):
    def __init__(self, items: list[DriveItem] | None = None) -> None:
        self._items = {i.id: i for i in (items or [])}

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
        return [], 0

    async def create(self, **kwargs: object) -> DriveItem:
        raise NotImplementedError

    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem:
        raise NotImplementedError

    async def update_parent(
        self, item_id: UUID, parent_id: UUID | None, updated_by: UUID
    ) -> DriveItem:
        raise NotImplementedError

    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        return False


def _svc(
    shares: list[Share] | None = None,
    items: list[DriveItem] | None = None,
) -> PermissionService:
    return PermissionService(
        share_repo=MemShareRepo(shares),
        item_repo=MemItemRepo(items),
    )


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_owner_gets_owner_permission() -> None:
    user = uuid4()
    item = _item(owner_id=user)
    svc = _svc()
    perm = await svc.get_permission(user, item)
    assert perm == Permission.OWNER


async def test_no_share_returns_none() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    svc = _svc()
    perm = await svc.get_permission(user, item)
    assert perm is None


async def test_direct_viewer_share() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.VIEWER)
    svc = _svc(shares=[share], items=[item])
    perm = await svc.get_permission(user, item)
    assert perm == Permission.VIEWER


async def test_direct_downloader_share() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.DOWNLOADER)
    svc = _svc(shares=[share], items=[item])
    perm = await svc.get_permission(user, item)
    assert perm == Permission.DOWNLOADER


async def test_direct_editor_share() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.EDITOR)
    svc = _svc(shares=[share], items=[item])
    perm = await svc.get_permission(user, item)
    assert perm == Permission.EDITOR


async def test_inherited_folder_permission() -> None:
    """Child inherits parent folder's share permission."""
    user = uuid4()
    folder_owner = uuid4()
    folder = _item(owner_id=folder_owner)
    child = _item(owner_id=folder_owner, parent_id=folder.id)
    share = _share(folder.id, user, Permission.EDITOR)
    svc = _svc(shares=[share], items=[folder, child])
    perm = await svc.get_permission(user, child)
    assert perm == Permission.EDITOR


async def test_owner_of_parent_gives_owner() -> None:
    """Owning a parent folder means OWNER on children."""
    user = uuid4()
    folder = _item(owner_id=user)
    child = _item(owner_id=uuid4(), parent_id=folder.id)
    svc = _svc(items=[folder, child])
    perm = await svc.get_permission(user, child)
    assert perm == Permission.OWNER


async def test_most_permissive_inherited_wins() -> None:
    """If ancestor has EDITOR and closer node has VIEWER, EDITOR wins."""
    user = uuid4()
    owner = uuid4()
    grandparent = _item(owner_id=owner)
    parent = _item(owner_id=owner, parent_id=grandparent.id)
    child = _item(owner_id=owner, parent_id=parent.id)
    # grandparent: editor, parent: viewer
    shares = [
        _share(grandparent.id, user, Permission.EDITOR),
        _share(parent.id, user, Permission.VIEWER),
    ]
    svc = _svc(shares=shares, items=[grandparent, parent, child])
    perm = await svc.get_permission(user, child)
    assert perm == Permission.EDITOR


async def test_assert_can_view_passes_for_viewer() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.VIEWER)
    svc = _svc(shares=[share], items=[item])
    await svc.assert_can_view(user, item)


async def test_assert_can_view_fails_for_none() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    svc = _svc()
    with pytest.raises(ForbiddenError):
        await svc.assert_can_view(user, item)


async def test_assert_can_download_fails_for_viewer() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.VIEWER)
    svc = _svc(shares=[share], items=[item])
    with pytest.raises(ForbiddenError):
        await svc.assert_can_download(user, item)


async def test_assert_can_download_passes_for_downloader() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.DOWNLOADER)
    svc = _svc(shares=[share], items=[item])
    await svc.assert_can_download(user, item)


async def test_assert_can_edit_fails_for_viewer() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.VIEWER)
    svc = _svc(shares=[share], items=[item])
    with pytest.raises(ForbiddenError):
        await svc.assert_can_edit(user, item)


async def test_assert_can_edit_passes_for_editor() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.EDITOR)
    svc = _svc(shares=[share], items=[item])
    await svc.assert_can_edit(user, item)


async def test_assert_is_owner_fails_for_editor() -> None:
    user = uuid4()
    item = _item(owner_id=uuid4())
    share = _share(item.id, user, Permission.EDITOR)
    svc = _svc(shares=[share], items=[item])
    with pytest.raises(ForbiddenError):
        await svc.assert_is_owner(user, item)


async def test_assert_is_owner_passes_for_owner() -> None:
    user = uuid4()
    item = _item(owner_id=user)
    svc = _svc()
    await svc.assert_is_owner(user, item)
