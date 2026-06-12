from __future__ import annotations

import hashlib
import io
from collections.abc import AsyncGenerator
from uuid import UUID, uuid4

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import ItemType
from app.file_version.repository import AbstractFileVersionRepository
from app.models.drive_item import DriveItem
from app.permission.service import PermissionService
from app.schemas.common import DriveItemResponse
from app.storage.base import StorageProvider
from app.users.service import QuotaService


def _make_storage_key(user_id: UUID, storage_uuid: UUID, version_no: int = 1) -> str:
    return f"users/{user_id}/files/{storage_uuid}/v{version_no}"


def _safe_filename(name: str) -> str:
    name = name.strip()
    if not name:
        raise AppError(ErrorCode.INVALID_OPERATION, "Filename cannot be empty")
    if len(name) > 512:
        raise AppError(ErrorCode.INVALID_OPERATION, "Filename too long (max 512 chars)")
    if any(c in name for c in "/\\\x00"):
        raise AppError(ErrorCode.INVALID_OPERATION, "Filename contains invalid characters")
    return name


def _split_name(name: str) -> tuple[str, str]:
    """Return (stem, ext) where ext includes the leading dot, or '' if no extension."""
    idx = name.rfind(".")
    if idx > 0:
        return name[:idx], name[idx:]
    return name, ""


def _to_response(item: DriveItem) -> DriveItemResponse:
    return DriveItemResponse(
        id=item.id,
        owner_id=item.owner_id,
        parent_id=item.parent_id,
        item_type=item.item_type,
        name=item.name,
        mime_type=item.mime_type,
        extension=item.extension,
        size_bytes=item.size_bytes,
        is_starred=False,
        is_deleted=item.is_deleted,
        deleted_at=item.deleted_at,
        created_by=item.created_by,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class UploadService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        version_repo: AbstractFileVersionRepository,
        storage: StorageProvider,
        permission_svc: PermissionService,
        quota_svc: QuotaService,
    ) -> None:
        self._items = item_repo
        self._versions = version_repo
        self._storage = storage
        self._perm = permission_svc
        self._quota = quota_svc

    async def upload_simple(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        filename: str,
        stream: AsyncGenerator[bytes, None],
        size_bytes: int,
        mime_type: str | None = None,
    ) -> DriveItemResponse:
        filename = _safe_filename(filename)
        stem, ext = _split_name(filename)

        parent_item: DriveItem | None = None
        if parent_id is not None:
            parent = await self._items.get_by_id(parent_id)
            if parent is None or parent.is_deleted:
                raise NotFoundError("Parent folder not found")
            if parent.item_type != ItemType.FOLDER:
                raise AppError(ErrorCode.INVALID_OPERATION, "Parent must be a folder")
            parent_item = parent
            await self._perm.assert_can_edit(user_id, parent_item)

        await self._quota.assert_has_space(user_id, size_bytes)

        # Resolve unique name by auto-incrementing on conflict
        final_name = filename
        counter = 1
        while await self._items.name_exists_in_parent(final_name, parent_id, user_id):
            final_name = f"{stem} ({counter}){ext}"
            counter += 1

        # Buffer stream and compute checksum
        chunks: list[bytes] = []
        sha = hashlib.sha256()
        async for chunk in stream:
            chunks.append(chunk)
            sha.update(chunk)
        data = b"".join(chunks)
        actual_size = len(data)
        checksum = sha.hexdigest()

        storage_key = _make_storage_key(user_id, uuid4())
        await self._storage.save(storage_key, io.BytesIO(data), size=actual_size)

        try:
            item = await self._items.create(
                owner_id=user_id,
                parent_id=parent_id,
                item_type=ItemType.FILE,
                name=final_name,
                created_by=user_id,
            )
            item.size_bytes = actual_size
            item.mime_type = mime_type
            item.extension = ext.lstrip(".") if ext else None
            item.checksum_sha256 = checksum
            item.storage_key = storage_key

            await self._versions.create(
                file_id=item.id,
                version_no=1,
                storage_key=storage_key,
                size_bytes=actual_size,
                checksum_sha256=checksum,
                created_by=user_id,
            )
            await self._quota.add_used_bytes(user_id, actual_size)
        except Exception:
            await self._storage.delete(storage_key)
            raise

        return _to_response(item)
