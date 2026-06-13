from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import IO
from uuid import uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError, QuotaExceededError
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.file_version import FileVersion
from app.models.share import Share
from app.models.user import User
from app.permission.service import PermissionService
from app.upload.service import UploadService
from app.users.service import QuotaService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.file_version.test_service import MemFileVersionRepo
from tests.permission.test_service import MemItemRepo, MemShareRepo
from tests.users.test_service import MockUserRepo

# ── Fake storage ─────────────────────────────────────────────────────────────


class MemStorage:
    def __init__(self, *, fail_save: bool = False) -> None:
        self._data: dict[str, bytes] = {}
        self.fail_save = fail_save
        self.deleted: list[str] = []

    async def save(self, key: str, data: IO[bytes], *, size: int | None = None) -> None:
        if self.fail_save:
            raise OSError("Storage failure")
        self._data[key] = data.read()

    def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        async def _gen() -> AsyncGenerator[bytes, None]:
            yield self._data.get(key, b"")

        return _gen()

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        return key in self._data

    async def get_size(self, key: str) -> int:
        return len(self._data.get(key, b""))


async def _stream(data: bytes) -> AsyncGenerator[bytes, None]:
    yield data


def _make_user(quota_bytes: int = 100 * 1024 * 1024, used_bytes: int = 0) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="test@test.com",
        username="test",
        password_hash="h",
        avatar_url=None,
        quota_bytes=quota_bytes,
        used_bytes=used_bytes,
        is_active=True,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _make_svc(
    items: list[DriveItem] | None = None,
    shares: list[Share] | None = None,
    storage: MemStorage | None = None,
    user: User | None = None,
) -> tuple[UploadService, MemDriveItemRepo, MemFileVersionRepo, MemStorage]:
    if storage is None:
        storage = MemStorage()
    if user is None:
        user = _make_user()
    item_repo = MemDriveItemRepo(items)
    version_repo = MemFileVersionRepo()
    perm_svc = PermissionService(
        share_repo=MemShareRepo(shares),
        item_repo=MemItemRepo(items),
    )
    quota_svc = QuotaService(repo=MockUserRepo(user))
    svc = UploadService(
        item_repo=item_repo,
        version_repo=version_repo,
        storage=storage,
        permission_svc=perm_svc,
        quota_svc=quota_svc,
    )
    return svc, item_repo, version_repo, storage


# ── Tests ────────────────────────────────────────────────────────────────────


async def test_upload_success() -> None:
    user = _make_user()
    svc, _, _, _ = _make_svc(user=user)
    content = b"hello world"
    resp = await svc.upload_simple(
        user_id=user.id,
        parent_id=None,
        filename="hello.txt",
        stream=_stream(content),
        size_bytes=len(content),
        mime_type="text/plain",
    )
    assert resp.name == "hello.txt"
    assert resp.item_type == ItemType.FILE
    assert resp.size_bytes == len(content)
    assert resp.mime_type == "text/plain"
    assert resp.extension == "txt"


async def test_upload_creates_drive_item() -> None:
    user = _make_user()
    svc, item_repo, _, _ = _make_svc(user=user)
    resp = await svc.upload_simple(
        user_id=user.id,
        parent_id=None,
        filename="doc.pdf",
        stream=_stream(b"pdf content"),
        size_bytes=11,
        mime_type="application/pdf",
    )
    # item should exist in repo
    found = await item_repo.get_by_id(resp.id)
    assert found is not None
    assert found.name == "doc.pdf"


async def test_upload_creates_file_version_v1() -> None:
    user = _make_user()
    svc, _, version_repo, _ = _make_svc(user=user)
    resp = await svc.upload_simple(
        user_id=user.id,
        parent_id=None,
        filename="img.png",
        stream=_stream(b"\x89PNG"),
        size_bytes=4,
    )
    versions = await version_repo.list_by_file(resp.id)
    assert len(versions) == 1
    assert versions[0].version_no == 1


async def test_upload_increases_quota() -> None:
    user = _make_user(quota_bytes=10_000, used_bytes=0)
    svc, _, _, _ = _make_svc(user=user)
    await svc.upload_simple(
        user_id=user.id,
        parent_id=None,
        filename="f.bin",
        stream=_stream(b"x" * 500),
        size_bytes=500,
    )
    assert user.used_bytes == 500


async def test_upload_quota_exceeded_raises() -> None:
    user = _make_user(quota_bytes=100, used_bytes=90)
    svc, _, _, _ = _make_svc(user=user)
    with pytest.raises(QuotaExceededError):
        await svc.upload_simple(
            user_id=user.id,
            parent_id=None,
            filename="big.bin",
            stream=_stream(b"x" * 50),
            size_bytes=50,
        )


async def test_upload_parent_not_found_raises() -> None:
    user = _make_user()
    svc, _, _, _ = _make_svc(user=user)
    with pytest.raises(NotFoundError):
        await svc.upload_simple(
            user_id=user.id,
            parent_id=uuid4(),
            filename="f.txt",
            stream=_stream(b"data"),
            size_bytes=4,
        )


async def test_upload_parent_not_folder_raises() -> None:
    user = _make_user()
    file_item = _item(owner_id=user.id, item_type=ItemType.FILE, name="existing.pdf")
    svc, _, _, _ = _make_svc(items=[file_item], user=user)
    with pytest.raises(AppError) as exc_info:
        await svc.upload_simple(
            user_id=user.id,
            parent_id=file_item.id,
            filename="f.txt",
            stream=_stream(b"data"),
            size_bytes=4,
        )
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_upload_no_permission_raises() -> None:
    owner = uuid4()
    user = _make_user()
    folder = _item(owner_id=owner, item_type=ItemType.FOLDER, name="Folder")
    # user has no share on folder
    svc, _, _, _ = _make_svc(items=[folder], user=user)
    with pytest.raises(ForbiddenError):
        await svc.upload_simple(
            user_id=user.id,
            parent_id=folder.id,
            filename="f.txt",
            stream=_stream(b"data"),
            size_bytes=4,
        )


async def test_upload_auto_rename_on_conflict() -> None:
    user = _make_user()
    existing = _item(owner_id=user.id, name="report.txt", item_type=ItemType.FILE)
    svc, _, _, _ = _make_svc(items=[existing], user=user)
    resp = await svc.upload_simple(
        user_id=user.id,
        parent_id=None,
        filename="report.txt",
        stream=_stream(b"new content"),
        size_bytes=11,
    )
    assert resp.name == "report (1).txt"


async def test_storage_failure_no_db_record() -> None:
    user = _make_user()
    bad_storage = MemStorage(fail_save=True)
    svc, item_repo, _, _ = _make_svc(storage=bad_storage, user=user)
    with pytest.raises(OSError):
        await svc.upload_simple(
            user_id=user.id,
            parent_id=None,
            filename="f.txt",
            stream=_stream(b"data"),
            size_bytes=4,
        )
    # No items should have been created
    assert len(item_repo._items) == 0


async def test_db_failure_cleans_up_storage() -> None:
    """If version_repo.create() raises, the storage file should be deleted."""
    user = _make_user()
    storage = MemStorage()
    item_repo = MemDriveItemRepo()
    perm_svc = PermissionService(
        share_repo=MemShareRepo(),
        item_repo=MemItemRepo(),
    )
    quota_svc = QuotaService(repo=MockUserRepo(user))

    class FailingVersionRepo(MemFileVersionRepo):
        async def create(self, **kwargs: object) -> FileVersion:
            raise RuntimeError("DB is down")

    svc = UploadService(
        item_repo=item_repo,
        version_repo=FailingVersionRepo(),
        storage=storage,
        permission_svc=perm_svc,
        quota_svc=quota_svc,
    )
    with pytest.raises(RuntimeError):
        await svc.upload_simple(
            user_id=user.id,
            parent_id=None,
            filename="f.txt",
            stream=_stream(b"data"),
            size_bytes=4,
        )
    # Storage file must have been cleaned up
    assert len(storage._data) == 0
    assert len(storage.deleted) == 1
