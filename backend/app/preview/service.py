from __future__ import annotations

import io
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
from app.preview.converter import ConversionError, convert_to_pdf, office_available
from app.storage.base import StorageProvider

_TEXT_MAX_BYTES = 65_536  # 64 KiB

# Office/CSV types rendered by converting to PDF via LibreOffice.
_OFFICE_EXTS = {"docx", "xlsx", "pptx", "doc", "xls", "ppt", "csv", "odt", "ods", "odp"}
_OFFICE_MIMES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/msword",
    "application/vnd.ms-excel",
    "application/vnd.ms-powerpoint",
    "application/vnd.oasis.opendocument.text",
    "application/vnd.oasis.opendocument.spreadsheet",
    "application/vnd.oasis.opendocument.presentation",
    "text/csv",
}
_MARKDOWN_EXTS = {"md", "markdown"}


class PreviewType(StrEnum):
    IMAGE = "image"
    PDF = "pdf"
    DOCUMENT = "document"  # Office/CSV → converted to PDF
    TEXT = "text"
    MARKDOWN = "markdown"
    VIDEO = "video"
    AUDIO = "audio"
    UNSUPPORTED = "unsupported"


class PreviewInfoResponse(BaseModel):
    item_id: UUID
    preview_type: PreviewType
    mime_type: str | None
    size_bytes: int
    filename: str


def _resolve_preview_type(
    mime_type: str | None, extension: str | None, *, office: bool
) -> PreviewType:
    ext = (extension or "").lower().lstrip(".")
    m = (mime_type or "").lower()
    # Markdown first — its MIME often starts with text/ and would be caught below.
    if ext in _MARKDOWN_EXTS or m == "text/markdown":
        return PreviewType.MARKDOWN
    # Office/CSV → PDF, only when LibreOffice is available; otherwise fall through
    # (csv lands on TEXT, the rest on UNSUPPORTED).
    if office and (ext in _OFFICE_EXTS or m in _OFFICE_MIMES):
        return PreviewType.DOCUMENT
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
        ptype = _resolve_preview_type(item.mime_type, item.extension, office=office_available())
        # Document is delivered as PDF; report that so the client uses the PDF viewer.
        mime = "application/pdf" if ptype == PreviewType.DOCUMENT else item.mime_type
        return PreviewInfoResponse(
            item_id=item.id,
            preview_type=ptype,
            mime_type=mime,
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
        ptype = _resolve_preview_type(item.mime_type, item.extension, office=office_available())
        if ptype == PreviewType.UNSUPPORTED:
            raise AppError(ErrorCode.INVALID_OPERATION, "File type not supported for preview")
        if ptype == PreviewType.DOCUMENT:
            return PreviewType.DOCUMENT, "application/pdf", await self._document_pdf_stream(item)
        if ptype == PreviewType.MARKDOWN:
            stream = _limited_text_stream(self._storage.open_read(item.storage_key))
            return PreviewType.MARKDOWN, "text/markdown", stream
        if ptype == PreviewType.TEXT:
            stream = _limited_text_stream(self._storage.open_read(item.storage_key))
            return ptype, item.mime_type or "text/plain", stream
        return (
            ptype,
            item.mime_type or "application/octet-stream",
            self._storage.open_read(item.storage_key),
        )

    async def _document_pdf_stream(self, item: DriveItem) -> AsyncGenerator[bytes, None]:
        """Return a PDF byte stream for an Office/CSV file, converting on demand and
        caching the result by the file's checksum."""
        checksum = item.checksum_sha256
        cache_key = f"preview-cache/{checksum}.pdf" if checksum else None
        if cache_key and await self._storage.exists(cache_key):
            return self._storage.open_read(cache_key)

        assert item.storage_key is not None  # checked by caller
        data = await _read_all(self._storage.open_read(item.storage_key))
        ext = (item.extension or "").lstrip(".")
        try:
            pdf = await convert_to_pdf(data, suffix=f".{ext}" if ext else ".bin")
        except ConversionError as exc:
            raise AppError(
                ErrorCode.INVALID_OPERATION, "Document could not be converted for preview"
            ) from exc
        if cache_key:
            await self._storage.save(cache_key, io.BytesIO(pdf), size=len(pdf))
        return _bytes_stream(pdf)


async def _read_all(source: AsyncGenerator[bytes, None]) -> bytes:
    return b"".join([chunk async for chunk in source])


async def _bytes_stream(data: bytes) -> AsyncGenerator[bytes, None]:
    yield data


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
