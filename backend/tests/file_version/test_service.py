from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError
from app.drive.schemas import ItemType
from app.file_version.repository import AbstractFileVersionRepository
from app.file_version.service import FileVersionService
from app.models.drive_item import DriveItem
from app.models.file_version import FileVersion
from app.models.share import Share
from app.permission.permissions import Permission
from app.permission.service import PermissionService
from tests.permission.test_service import MemItemRepo, MemShareRepo, _item, _share

# ── Fake repositories ────────────────────────────────────────────────────────


class MemFileVersionRepo(AbstractFileVersionRepository):
    def __init__(self) -> None:
        self._versions: list[FileVersion] = []

    async def create(
        self,
        *,
        file_id: UUID,
        version_no: int,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None,
        created_by: UUID,
    ) -> FileVersion:
        v = FileVersion(
            id=uuid4(),
            file_id=file_id,
            version_no=version_no,
            storage_key=storage_key,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._versions.append(v)
        return v

    async def get_max_version_no(self, file_id: UUID) -> int:
        nos = [v.version_no for v in self._versions if v.file_id == file_id]
        return max(nos, default=0)

    async def list_by_file(self, file_id: UUID) -> list[FileVersion]:
        return sorted(
            [v for v in self._versions if v.file_id == file_id],
            key=lambda v: v.version_no,
            reverse=True,
        )


def _file_item(owner_id: UUID) -> DriveItem:
    return _item(owner_id=owner_id, item_type=ItemType.FILE)


def _folder_item(owner_id: UUID) -> DriveItem:
    return _item(owner_id=owner_id, item_type=ItemType.FOLDER)


def _svc(
    shares: list[Share] | None = None,
    items: list[DriveItem] | None = None,
) -> tuple[FileVersionService, MemFileVersionRepo]:
    repo = MemFileVersionRepo()
    perm_svc = PermissionService(
        share_repo=MemShareRepo(shares),
        item_repo=MemItemRepo(items),
    )
    svc = FileVersionService(version_repo=repo, permission_svc=perm_svc)
    return svc, repo


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_create_v1() -> None:
    user = uuid4()
    file = _file_item(user)
    svc, _ = _svc(items=[file])
    v = await svc.create_version(user, file, storage_key="k/v1", size_bytes=1024)
    assert v.version_no == 1
    assert v.file_id == file.id
    assert v.size_bytes == 1024


async def test_create_v2_increments() -> None:
    user = uuid4()
    file = _file_item(user)
    svc, _ = _svc(items=[file])
    v1 = await svc.create_version(user, file, storage_key="k/v1", size_bytes=100)
    v2 = await svc.create_version(user, file, storage_key="k/v2", size_bytes=200)
    assert v1.version_no == 1
    assert v2.version_no == 2


async def test_folder_cannot_have_version() -> None:
    user = uuid4()
    folder = _folder_item(user)
    svc, _ = _svc(items=[folder])
    with pytest.raises(AppError) as exc_info:
        await svc.create_version(user, folder, storage_key="k", size_bytes=0)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_viewer_cannot_create_version() -> None:
    owner = uuid4()
    user = uuid4()
    file = _file_item(owner)
    share = _share(file.id, user, Permission.VIEWER)
    svc, _ = _svc(shares=[share], items=[file])
    with pytest.raises(ForbiddenError):
        await svc.create_version(user, file, storage_key="k", size_bytes=100)


async def test_editor_can_create_version() -> None:
    owner = uuid4()
    user = uuid4()
    file = _file_item(owner)
    share = _share(file.id, user, Permission.EDITOR)
    svc, _ = _svc(shares=[share], items=[file])
    v = await svc.create_version(user, file, storage_key="k/v1", size_bytes=512)
    assert v.version_no == 1


async def test_list_versions_sorted_desc() -> None:
    user = uuid4()
    file = _file_item(user)
    svc, _ = _svc(items=[file])
    await svc.create_version(user, file, storage_key="k/v1", size_bytes=100)
    await svc.create_version(user, file, storage_key="k/v2", size_bytes=200)
    await svc.create_version(user, file, storage_key="k/v3", size_bytes=300)
    versions = await svc.list_versions(user, file)
    assert [v.version_no for v in versions] == [3, 2, 1]


async def test_list_versions_requires_view_permission() -> None:
    owner = uuid4()
    other = uuid4()
    file = _file_item(owner)
    svc, _ = _svc(items=[file])
    with pytest.raises(ForbiddenError):
        await svc.list_versions(other, file)


async def test_list_versions_folder_raises() -> None:
    user = uuid4()
    folder = _folder_item(user)
    svc, _ = _svc(items=[folder])
    with pytest.raises(AppError) as exc_info:
        await svc.list_versions(user, folder)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_version_size_bytes_recorded() -> None:
    user = uuid4()
    file = _file_item(user)
    svc, _ = _svc(items=[file])
    await svc.create_version(user, file, storage_key="k/v1", size_bytes=9999)
    versions = await svc.list_versions(user, file)
    assert versions[0].size_bytes == 9999
