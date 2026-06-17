from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.activity_log.actions import ActivityAction
from app.activity_log.service import ActivityLogService
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import ItemType
from app.file_version.repository import AbstractFileVersionRepository
from app.models.drive_item import DriveItem
from app.permission.repository import AbstractShareRepository
from app.schemas.common import DriveItemResponse, Page
from app.storage.base import StorageProvider
from app.trash.repository import AbstractTrashRepository
from app.upload.service import _split_name, _to_response
from app.users.service import QuotaService


class TrashService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        trash_repo: AbstractTrashRepository,
        version_repo: AbstractFileVersionRepository,
        share_repo: AbstractShareRepository,
        storage: StorageProvider,
        quota_svc: QuotaService,
        activity_svc: ActivityLogService | None = None,
    ) -> None:
        self._items = item_repo
        self._trash = trash_repo
        self._versions = version_repo
        self._shares = share_repo
        self._storage = storage
        self._quota = quota_svc
        self._activity = activity_svc

    async def trash_item(self, user_id: UUID, item_id: UUID) -> DriveItemResponse:
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found")
        if item.owner_id != user_id:
            raise ForbiddenError()
        if item.is_deleted:
            raise AppError(ErrorCode.INVALID_OPERATION, "Item is already in trash")
        item = await self._trash.mark_deleted(item_id, datetime.now(UTC))
        if self._activity:
            await self._activity.log(actor_id=user_id, action=ActivityAction.TRASH, item_id=item_id)
        return _to_response(item)

    async def list_trash(
        self, user_id: UUID, *, page: int = 1, page_size: int = 50
    ) -> Page[DriveItemResponse]:
        offset = (page - 1) * page_size
        items, total = await self._trash.list_deleted(user_id, offset=offset, limit=page_size)
        return Page.create(
            [_to_response(i) for i in items],
            total,
            page=page,
            page_size=page_size,
        )

    async def restore(self, user_id: UUID, item_id: UUID) -> DriveItemResponse:
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found")
        if item.owner_id != user_id:
            raise ForbiddenError()
        if not item.is_deleted:
            raise AppError(ErrorCode.INVALID_OPERATION, "Item is not in trash")

        # Determine restore destination — fall back to root if parent is gone
        parent_id: UUID | None = item.parent_id
        if parent_id is not None:
            parent = await self._items.get_by_id(parent_id)
            if parent is None or parent.is_deleted:
                parent_id = None

        # Resolve name conflicts in the destination
        name = item.name
        counter = 1
        while await self._items.name_exists_in_parent(name, parent_id, user_id):
            stem, ext = _split_name(item.name)
            name = f"{stem} ({counter}){ext}"
            counter += 1

        item = await self._trash.mark_restored(item_id)
        if parent_id != item.parent_id:
            item = await self._items.update_parent(item_id, parent_id, user_id)
        if name != item.name:
            item = await self._items.update_name(item_id, name, user_id)

        if self._activity:
            await self._activity.log(
                actor_id=user_id, action=ActivityAction.RESTORE, item_id=item_id
            )
        return _to_response(item)

    async def _free_file_storage(self, item: DriveItem) -> int:
        """Delete storage objects and version rows for a file. Returns bytes freed.

        The ``file_versions`` rows must be removed before the ``drive_items`` row
        (FK ``file_versions.file_id`` → ``drive_items.id``), otherwise the
        subsequent hard delete violates the constraint.
        """
        freed = 0
        for version in await self._versions.list_by_file(item.id):
            if await self._storage.exists(version.storage_key):
                freed += await self._storage.get_size(version.storage_key)
                await self._storage.delete(version.storage_key)
        await self._versions.delete_by_file(item.id)
        return freed

    async def permanent_delete(self, user_id: UUID, item_id: UUID) -> None:
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found")
        if item.owner_id != user_id:
            raise ForbiddenError()
        if not item.is_deleted:
            raise AppError(
                ErrorCode.INVALID_OPERATION, "Item must be trashed before permanent deletion"
            )

        total_freed = 0

        if item.item_type == ItemType.FILE:
            total_freed += await self._free_file_storage(item)
        else:
            descendants = await self._trash.get_children_recursive(item_id)
            for child in descendants:
                if child.item_type == ItemType.FILE:
                    total_freed += await self._free_file_storage(child)
                await self._shares.delete_by_item(child.id)
                await self._trash.hard_delete(child.id)

        await self._shares.delete_by_item(item_id)
        await self._trash.hard_delete(item_id)

        if total_freed > 0:
            await self._quota.subtract_used_bytes(user_id, total_freed)

        if self._activity:
            await self._activity.log(
                actor_id=user_id,
                action=ActivityAction.PERMANENT_DELETE,
                item_id=item_id,
            )

    async def empty_trash(self, user_id: UUID) -> None:
        all_deleted = await self._trash.get_all_deleted(user_id)
        deleted_ids = {i.id for i in all_deleted}
        # Only process items whose parent is not also being deleted (avoid double-processing)
        top_level = [
            i for i in all_deleted if i.parent_id is None or i.parent_id not in deleted_ids
        ]
        for item in top_level:
            await self.permanent_delete(user_id, item.id)
