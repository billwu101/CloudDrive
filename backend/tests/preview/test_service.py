from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.permission.service import PermissionService
from app.preview.service import _TEXT_MAX_BYTES, PreviewService, PreviewType
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.permission.test_service import MemItemRepo, MemShareRepo
from tests.upload.test_service import MemStorage


def _file(
    owner_id: UUID,
    *,
    storage_key: str | None = "k/v1",
    mime_type: str | None = "text/plain",
) -> DriveItem:
    item = _item(owner_id=owner_id, item_type=ItemType.FILE, name="file.txt")
    item.storage_key = storage_key
    item.mime_type = mime_type
    item.size_bytes = 100
    return item


def _make_svc(
    items: list[DriveItem] | None = None,
    shares: list[Share] | None = None,
    storage: MemStorage | None = None,
) -> PreviewService:
    if storage is None:
        storage = MemStorage()
    return PreviewService(
        item_repo=MemDriveItemRepo(items),
        storage=storage,
        permission_svc=PermissionService(
            share_repo=MemShareRepo(shares),
            item_repo=MemItemRepo(items),
        ),
    )


async def test_image_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="image/jpeg")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.IMAGE


async def test_pdf_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="application/pdf")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.PDF


async def test_text_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="text/plain")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.TEXT


async def test_unsupported_preview_info() -> None:
    user = uuid4()
    file = _file(user, mime_type="application/octet-stream")
    svc = _make_svc(items=[file])
    info = await svc.get_info(user, file.id)
    assert info.preview_type == PreviewType.UNSUPPORTED


async def test_folder_cannot_be_previewed() -> None:
    user = uuid4()
    folder = _item(owner_id=user, item_type=ItemType.FOLDER, name="folder")
    svc = _make_svc(items=[folder])
    with pytest.raises(AppError) as exc_info:
        await svc.get_info(user, folder.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_no_permission_cannot_preview() -> None:
    owner = uuid4()
    other = uuid4()
    file = _file(owner)
    svc = _make_svc(items=[file])
    with pytest.raises(ForbiddenError):
        await svc.get_info(other, file.id)


async def test_text_preview_does_not_exceed_limit() -> None:
    user = uuid4()
    storage = MemStorage()
    large_content = b"x" * (_TEXT_MAX_BYTES + 1000)
    storage._data["k/v1"] = large_content
    file = _file(user, mime_type="text/plain")

    # MemStorage.open_read reads from _data directly
    svc = _make_svc(items=[file], storage=storage)
    _, _, stream = await svc.get_content(user, file.id)
    chunks = [c async for c in stream]
    assert len(b"".join(chunks)) <= _TEXT_MAX_BYTES


async def test_unsupported_content_raises() -> None:
    user = uuid4()
    storage = MemStorage()
    storage._data["k/v1"] = b"binary"
    file = _file(user, mime_type="application/octet-stream")
    svc = _make_svc(items=[file], storage=storage)
    with pytest.raises(AppError) as exc_info:
        await svc.get_content(user, file.id)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION
