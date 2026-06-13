from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.file_version import FileVersion
from app.models.share import Share
from app.trash.repository import AbstractTrashRepository
from app.trash.service import TrashService
from app.users.service import QuotaService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.file_version.test_service import MemFileVersionRepo
from tests.permission.test_service import MemShareRepo
from tests.upload.test_service import MemStorage, _make_user
from tests.users.test_service import MockUserRepo

# ── In-memory trash repository ───────────────────────────────────────────────


class MemTrashRepo(AbstractTrashRepository):
    def __init__(self, items: dict[UUID, DriveItem]) -> None:
        self._items = items  # shared reference with MemDriveItemRepo

    async def mark_deleted(self, item_id: UUID, deleted_at: datetime) -> DriveItem:
        item = self._items[item_id]
        item.is_deleted = True
        item.deleted_at = deleted_at
        return item

    async def mark_restored(self, item_id: UUID) -> DriveItem:
        item = self._items[item_id]
        item.is_deleted = False
        item.deleted_at = None
        return item

    async def list_deleted(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[DriveItem], int]:
        matched = [i for i in self._items.values() if i.owner_id == owner_id and i.is_deleted]
        return matched[offset : offset + limit], len(matched)

    async def get_all_deleted(self, owner_id: UUID) -> list[DriveItem]:
        return [i for i in self._items.values() if i.owner_id == owner_id and i.is_deleted]

    async def hard_delete(self, item_id: UUID) -> None:
        self._items.pop(item_id, None)

    async def get_children_recursive(self, item_id: UUID) -> list[DriveItem]:
        result: list[DriveItem] = []
        queue = [item_id]
        while queue:
            parent_ids = set(queue)
            children = [i for i in self._items.values() if i.parent_id in parent_ids]
            result.extend(children)
            queue = [c.id for c in children]
        return result


# ── Helpers ──────────────────────────────────────────────────────────────────


def _file(owner_id: UUID, *, parent_id: UUID | None = None, storage_key: str = "k/v1") -> DriveItem:
    item = _item(owner_id=owner_id, parent_id=parent_id, item_type=ItemType.FILE, name="file.txt")
    item.storage_key = storage_key
    item.mime_type = "text/plain"
    item.size_bytes = 100
    return item


def _make_svc(
    items: list[DriveItem] | None = None,
    shares: list[Share] | None = None,
    storage: MemStorage | None = None,
    version_repo: MemFileVersionRepo | None = None,
) -> tuple[TrashService, MemDriveItemRepo, MemFileVersionRepo, MemStorage, MemShareRepo]:
    if storage is None:
        storage = MemStorage()
    if version_repo is None:
        version_repo = MemFileVersionRepo()
    user = _make_user()
    item_repo = MemDriveItemRepo(items)
    share_repo = MemShareRepo(shares)
    trash_repo = MemTrashRepo(item_repo._items)
    quota_svc = QuotaService(repo=MockUserRepo(user))
    svc = TrashService(
        item_repo=item_repo,
        trash_repo=trash_repo,
        version_repo=version_repo,
        share_repo=share_repo,
        storage=storage,
        quota_svc=quota_svc,
    )
    return svc, item_repo, version_repo, storage, share_repo


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_trash_item_sets_deleted() -> None:
    user = uuid4()
    item = _item(owner_id=user, name="doc.txt", item_type=ItemType.FILE)
    svc, repo, _, _, _ = _make_svc(items=[item])
    resp = await svc.trash_item(user, item.id)
    assert resp.is_deleted is True
    assert resp.deleted_at is not None
    assert repo._items[item.id].is_deleted is True


async def test_trash_item_not_found_raises() -> None:
    svc, _, _, _, _ = _make_svc()
    with pytest.raises(NotFoundError):
        await svc.trash_item(uuid4(), uuid4())


async def test_trash_item_non_owner_raises() -> None:
    owner = uuid4()
    other = uuid4()
    item = _item(owner_id=owner)
    svc, _, _, _, _ = _make_svc(items=[item])
    with pytest.raises(ForbiddenError):
        await svc.trash_item(other, item.id)


async def test_trash_already_trashed_raises() -> None:
    user = uuid4()
    item = _item(owner_id=user, is_deleted=True)
    svc, _, _, _, _ = _make_svc(items=[item])
    with pytest.raises(AppError) as exc_info:
        await svc.trash_item(user, item.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_list_trash_returns_deleted_items() -> None:
    user = uuid4()
    deleted = _item(owner_id=user, name="gone.txt", is_deleted=True)
    active = _item(owner_id=user, name="here.txt")
    svc, _, _, _, _ = _make_svc(items=[deleted, active])
    page = await svc.list_trash(user, page=1, page_size=50)
    assert page.total == 1
    assert page.items[0].name == "gone.txt"


async def test_restore_item() -> None:
    user = uuid4()
    item = _item(owner_id=user, is_deleted=True)
    svc, repo, _, _, _ = _make_svc(items=[item])
    resp = await svc.restore(user, item.id)
    assert resp.is_deleted is False
    assert repo._items[item.id].is_deleted is False


async def test_restore_parent_deleted_fallback_to_root() -> None:
    user = uuid4()
    parent = _item(owner_id=user, name="folder", is_deleted=True)
    child = _item(owner_id=user, parent_id=parent.id, name="file.txt", is_deleted=True)
    svc, _repo, _, _, _ = _make_svc(items=[parent, child])
    resp = await svc.restore(user, child.id)
    assert resp.parent_id is None  # fell back to root


async def test_restore_name_conflict_auto_renamed() -> None:
    user = uuid4()
    existing = _item(owner_id=user, name="report.txt")
    deleted = _item(owner_id=user, name="report.txt", is_deleted=True)
    svc, _, _, _, _ = _make_svc(items=[existing, deleted])
    resp = await svc.restore(user, deleted.id)
    assert resp.name == "report (1).txt"


async def test_permanent_delete_removes_storage() -> None:
    user_obj = _make_user()
    storage = MemStorage()
    storage._data["k/v1"] = b"x" * 100
    item = _file(user_obj.id, storage_key="k/v1")
    item.is_deleted = True
    version_repo = MemFileVersionRepo()
    now = datetime.now(UTC)
    version = FileVersion(
        id=uuid4(),
        file_id=item.id,
        version_no=1,
        storage_key="k/v1",
        size_bytes=100,
        checksum_sha256=None,
        created_by=user_obj.id,
        created_at=now,
    )
    version_repo._versions.append(version)

    item_repo = MemDriveItemRepo([item])
    share_repo = MemShareRepo()
    trash_repo = MemTrashRepo(item_repo._items)
    quota_svc = QuotaService(repo=MockUserRepo(user_obj))

    svc = TrashService(
        item_repo=item_repo,
        trash_repo=trash_repo,
        version_repo=version_repo,
        share_repo=share_repo,
        storage=storage,
        quota_svc=quota_svc,
    )
    await svc.permanent_delete(user_obj.id, item.id)
    assert "k/v1" in storage.deleted
    assert item.id not in item_repo._items


async def test_permanent_delete_subtracts_quota() -> None:
    user_obj = _make_user(used_bytes=500)
    storage = MemStorage()
    storage._data["k/v1"] = b"x" * 200
    item = _file(user_obj.id, storage_key="k/v1")
    item.is_deleted = True
    version_repo = MemFileVersionRepo()
    now = datetime.now(UTC)
    version = FileVersion(
        id=uuid4(),
        file_id=item.id,
        version_no=1,
        storage_key="k/v1",
        size_bytes=200,
        checksum_sha256=None,
        created_by=user_obj.id,
        created_at=now,
    )
    version_repo._versions.append(version)

    item_repo = MemDriveItemRepo([item])
    trash_repo = MemTrashRepo(item_repo._items)
    quota_svc = QuotaService(repo=MockUserRepo(user_obj))

    svc = TrashService(
        item_repo=item_repo,
        trash_repo=trash_repo,
        version_repo=version_repo,
        share_repo=MemShareRepo(),
        storage=storage,
        quota_svc=quota_svc,
    )
    await svc.permanent_delete(user_obj.id, item.id)
    assert user_obj.used_bytes == 300


async def test_permanent_delete_folder_recursively_deletes_children() -> None:
    user_obj = _make_user()
    storage = MemStorage()
    storage._data["child_key"] = b"x" * 50

    folder = _item(owner_id=user_obj.id, item_type=ItemType.FOLDER, name="folder")
    folder.is_deleted = True
    child_file = _file(user_obj.id, parent_id=folder.id, storage_key="child_key")

    version_repo = MemFileVersionRepo()
    now = datetime.now(UTC)
    version = FileVersion(
        id=uuid4(),
        file_id=child_file.id,
        version_no=1,
        storage_key="child_key",
        size_bytes=50,
        checksum_sha256=None,
        created_by=user_obj.id,
        created_at=now,
    )
    version_repo._versions.append(version)

    item_repo = MemDriveItemRepo([folder, child_file])
    trash_repo = MemTrashRepo(item_repo._items)
    quota_svc = QuotaService(repo=MockUserRepo(user_obj))

    svc = TrashService(
        item_repo=item_repo,
        trash_repo=trash_repo,
        version_repo=version_repo,
        share_repo=MemShareRepo(),
        storage=storage,
        quota_svc=quota_svc,
    )
    await svc.permanent_delete(user_obj.id, folder.id)
    assert folder.id not in item_repo._items
    assert child_file.id not in item_repo._items
    assert "child_key" in storage.deleted
