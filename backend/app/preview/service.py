from __future__ import annotations

from collections.abc import AsyncGenerator
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.permission.service import PermissionService
from app.storage.base import StorageProvider

_TEXT_MAX_BYTES = 65_536  # 64 KiB


class PreviewType(StrEnum):
    IMAGE = "image"
    PDF = "pdf"
    TEXT = "text"
    VIDEO = "video"
    AUDIO = "audio"
    UNSUPPORTED = "unsupported"


class PreviewInfoResponse(BaseModel):
    item_id: UUID
    preview_type: PreviewType
    mime_type: str | None
    size_bytes: int
    filename: str


def _resolve_preview_type(mime_type: str | None) -> PreviewType:
    if mime_type is None:
        return PreviewType.UNSUPPORTED
    m = mime_type.lower()
    if m.startswith("image/"):
        return PreviewType.IMAGE
    if m == "application/pdf":
        return PreviewType.PDF
    if m.startswith("text/"):
        return PreviewType.TEXT
    if m.startswith("video/"):
        return PreviewType.VIDEO
    if m.startswith("audio/"):
        return PreviewType.AUDIO
    return PreviewType.UNSUPPORTED


class PreviewService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        storage: StorageProvider,
        permission_svc: PermissionService,
    ) -> None:
        self._items = item_repo
        self._storage = storage
        self._perm = permission_svc

    async def _get_file(self, user_id: UUID, item_id: UUID) -> DriveItem:
        item = await self._items.get_by_id(item_id)
        if item is None or item.is_deleted:
            raise AppError(ErrorCode.NOT_FOUND, "Item not found", status_code=404)
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot preview a folder")
        await self._perm.assert_can_view(user_id, item)
        return item

    async def get_info(self, user_id: UUID, item_id: UUID) -> PreviewInfoResponse:
        item = await self._get_file(user_id, item_id)
        return PreviewInfoResponse(
            item_id=item.id,
            preview_type=_resolve_preview_type(item.mime_type),
            mime_type=item.mime_type,
            size_bytes=item.size_bytes,
            filename=item.name,
        )

    async def get_content(
        self, user_id: UUID, item_id: UUID
    ) -> tuple[PreviewType, str, AsyncGenerator[bytes, None]]:
        """Returns (preview_type, effective_mime_type, byte_stream)."""
        item = await self._get_file(user_id, item_id)
        if not item.storage_key or not await self._storage.exists(item.storage_key):
            raise AppError(
                ErrorCode.ITEM_CONTENT_NOT_FOUND, "File content not found", status_code=404
            )
        preview_type = _resolve_preview_type(item.mime_type)
        if preview_type == PreviewType.UNSUPPORTED:
            raise AppError(ErrorCode.INVALID_OPERATION, "File type not supported for preview")
        effective_mime = item.mime_type or "application/octet-stream"
        if preview_type == PreviewType.TEXT:
            stream = _limited_text_stream(self._storage.open_read(item.storage_key))
        else:
            stream = self._storage.open_read(item.storage_key)
        return preview_type, effective_mime, stream


async def _limited_text_stream(
    source: AsyncGenerator[bytes, None],
) -> AsyncGenerator[bytes, None]:
    total = 0
    async for chunk in source:
        remaining = _TEXT_MAX_BYTES - total
        if remaining <= 0:
            break
        if len(chunk) > remaining:
            chunk = chunk[:remaining]
        yield chunk
        total += len(chunk)
