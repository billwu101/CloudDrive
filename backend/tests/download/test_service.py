from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError
from app.download.service import DownloadService
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.permission.permissions import Permission
from app.permission.service import PermissionService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.permission.test_service import MemItemRepo, MemShareRepo, _share
from tests.upload.test_service import MemStorage


def _file(owner_id: UUID, *, storage_key: str | None = "k/v1") -> DriveItem:
    item = _item(owner_id=owner_id, item_type=ItemType.FILE, name="file.txt")
    item.storage_key = storage_key
    item.mime_type = "text/plain"
    item.size_bytes = 11
    return item


def _make_svc(
    items: list[DriveItem] | None = None,
    shares: list[Share] | None = None,
    storage: MemStorage | None = None,
) -> DownloadService:
    if storage is None:
        storage = MemStorage()
    return DownloadService(
        item_repo=MemDriveItemRepo(items),
        storage=storage,
        permission_svc=PermissionService(
            share_repo=MemShareRepo(shares),
            item_repo=MemItemRepo(items),
        ),
    )


async def test_owner_can_download() -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/v1"] = b"hello world"
    file = _file(user)
    svc = _make_svc(items=[file], storage=storage)
    result = await svc.download(user, file.id)
    assert result.filename == "file.txt"
    assert result.size_bytes == 11


async def test_downloader_can_download() -> None:
    owner = uuid4()
    user = uuid4()
    storage = MemStorage()
    storage._data["k/v1"] = b"content"
    file = _file(owner)
    share = _share(file.id, user, Permission.DOWNLOADER)
    svc = _make_svc(items=[file], shares=[share], storage=storage)
    result = await svc.download(user, file.id)
    assert result.filename == "file.txt"


async def test_viewer_cannot_download() -> None:
    owner = uuid4()
    user = uuid4()
    file = _file(owner)
    share = _share(file.id, user, Permission.VIEWER)
    svc = _make_svc(items=[file], shares=[share])
    with pytest.raises(ForbiddenError):
        await svc.download(user, file.id)


async def test_folder_cannot_be_downloaded() -> None:
    user = uuid4()
    folder = _item(owner_id=user, item_type=ItemType.FOLDER, name="Folder")
    svc = _make_svc(items=[folder])
    with pytest.raises(AppError) as exc_info:
        await svc.download(user, folder.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_content_not_found_raises() -> None:
    user = uuid4()
    file = _file(user, storage_key="k/v1")
    # Storage is empty
    svc = _make_svc(items=[file])
    with pytest.raises(AppError) as exc_info:
        await svc.download(user, file.id)
    assert exc_info.value.code == ErrorCode.ITEM_CONTENT_NOT_FOUND


async def test_no_storage_key_raises() -> None:
    user = uuid4()
    file = _file(user, storage_key=None)
    svc = _make_svc(items=[file])
    with pytest.raises(AppError) as exc_info:
        await svc.download(user, file.id)
    assert exc_info.value.code == ErrorCode.ITEM_CONTENT_NOT_FOUND


async def test_download_stream_matches_content() -> None:
    user = uuid4()
    storage = MemStorage()
    content = b"test file data"
    storage._data["k/v1"] = content
    file = _file(user)

    # MemStorage.open_read already reads from _data, no need to patch

    svc = _make_svc(items=[file], storage=storage)
    result = await svc.download(user, file.id)
    chunks = [chunk async for chunk in result.stream]
    assert b"".join(chunks) == content
