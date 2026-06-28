from __future__ import annotations

import tempfile
import zipfile
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import DriveItemSortField, ItemType
from app.models.drive_item import DriveItem
from app.permission.service import PermissionService
from app.schemas.common import SortOrder
from app.storage.base import StorageProvider

# Page size when walking a folder's children for the archive. Folders are
# expected to be small; we still page so a huge folder cannot load all rows
# into memory at once.
_FOLDER_PAGE = 500


@dataclass
class DownloadFileResult:
    filename: str
    mime_type: str
    size_bytes: int
    stream: AsyncGenerator[bytes, None]


@dataclass
class ArchiveResult:
    filename: str
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

    async def archive(self, user_id: UUID, item_ids: list[UUID]) -> ArchiveResult:
        """Bundle one or more items (files and/or folders) into a single zip.

        Folders are walked recursively and their structure is preserved inside
        the archive. Every file is permission-checked individually; files whose
        blob is missing are skipped rather than failing the whole download.
        """
        if not item_ids:
            raise AppError(ErrorCode.INVALID_OPERATION, "No items selected to download")

        files: list[tuple[str, str]] = []  # (arcname inside zip, storage_key)
        used_top: set[str] = set()
        for item_id in item_ids:
            item = await self._items.get_by_id(item_id)
            if item is None or item.is_deleted:
                raise AppError(ErrorCode.NOT_FOUND, "Item not found", status_code=404)
            await self._perm.assert_can_download(user_id, item)
            top_name = self._dedupe(used_top, item.name)
            if item.item_type == ItemType.FILE:
                await self._maybe_add(files, top_name, item)
            else:
                await self._collect_folder(user_id, item, top_name, files)

        if not files:
            raise AppError(ErrorCode.INVALID_OPERATION, "Selection contains no downloadable files")
        return ArchiveResult(filename="download.zip", stream=self._build_zip(files))

    @staticmethod
    def _dedupe(used: set[str], name: str) -> str:
        """Give a top-level entry a unique name (``a.txt`` -> ``a (1).txt``)."""
        if name not in used:
            used.add(name)
            return name
        stem, dot, ext = name.rpartition(".")
        base, suffix = (stem, f".{ext}") if dot else (name, "")
        i = 1
        while True:
            candidate = f"{base} ({i}){suffix}"
            if candidate not in used:
                used.add(candidate)
                return candidate
            i += 1

    async def _maybe_add(self, files: list[tuple[str, str]], arcname: str, item: DriveItem) -> None:
        if item.storage_key and await self._storage.exists(item.storage_key):
            files.append((arcname, item.storage_key))

    async def _collect_folder(
        self,
        user_id: UUID,
        folder: DriveItem,
        prefix: str,
        files: list[tuple[str, str]],
    ) -> None:
        offset = 0
        while True:
            children, total = await self._items.list_children(
                folder.id,
                folder.owner_id,
                sort_by=DriveItemSortField.NAME,
                order=SortOrder.ASC,
                offset=offset,
                limit=_FOLDER_PAGE,
            )
            if not children:
                break
            for child in children:
                path = f"{prefix}/{child.name}"
                if child.item_type == ItemType.FILE:
                    await self._perm.assert_can_download(user_id, child)
                    await self._maybe_add(files, path, child)
                else:
                    await self._collect_folder(user_id, child, path, files)
            offset += len(children)
            if offset >= total:
                break

    async def _build_zip(self, files: list[tuple[str, str]]) -> AsyncGenerator[bytes, None]:
        # Spool to memory up to 32 MiB, then to a temp file — avoids holding a
        # large archive entirely in RAM while still being fast for small ones.
        with tempfile.SpooledTemporaryFile(max_size=32 * 1024 * 1024) as spool:
            # The ZipFile must be closed (its central directory flushed) before
            # we rewind and stream the bytes out.
            with zipfile.ZipFile(spool, "w", zipfile.ZIP_DEFLATED) as zf:
                for arcname, key in files:
                    with zf.open(arcname, "w") as dest:
                        async for chunk in self._storage.open_read(key):
                            dest.write(chunk)
            spool.seek(0)
            while True:
                chunk = spool.read(65536)
                if not chunk:
                    break
                yield chunk
