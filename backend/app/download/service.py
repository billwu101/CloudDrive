from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import ItemType
from app.permission.service import PermissionService
from app.storage.base import StorageProvider


@dataclass
class DownloadFileResult:
    filename: str
    mime_type: str
    size_bytes: int
    stream: AsyncGenerator[bytes, None]


class DownloadService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        storage: StorageProvider,
        permission_svc: PermissionService,
    ) -> None:
        self._items = item_repo
        self._storage = storage
        self._perm = permission_svc

    async def download(self, user_id: UUID, item_id: UUID) -> DownloadFileResult:
        item = await self._items.get_by_id(item_id)
        if item is None or item.is_deleted:
            raise AppError(ErrorCode.NOT_FOUND, "Item not found", status_code=404)
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot download a folder")
        await self._perm.assert_can_download(user_id, item)
        if not item.storage_key or not await self._storage.exists(item.storage_key):
            raise AppError(
                ErrorCode.ITEM_CONTENT_NOT_FOUND, "File content not found", status_code=404
            )
        return DownloadFileResult(
            filename=item.name,
            mime_type=item.mime_type or "application/octet-stream",
            size_bytes=item.size_bytes,
            stream=self._storage.open_read(item.storage_key),
        )
