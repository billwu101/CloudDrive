from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
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


@runtime_checkable
class SnapshotReferenceChecker(Protocol):
    """Narrow view of the snapshot store: can a blob still be reached by a
    snapshot? Lets permanent-delete avoid removing blobs Time Machine needs,
    without depending on the whole snapshot repository."""

    async def is_referenced_by_snapshot(self, storage_key: str) -> bool: ...


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
        snapshot_refs: SnapshotReferenceChecker | None = None,
    ) -> None:
        self._items = item_repo
        self._trash = trash_repo
        self._versions = version_repo
        self._shares = share_repo
        self._storage = storage
        self._quota = quota_svc
        self._activity = activity_svc
        # When set, blobs still referenced by a snapshot are left for GC instead
        # of being deleted here. When None, no blob is deleted on permanent
        # delete (the safe default) — GC reclaims it once it's truly orphaned.
        self._snapshot_refs = snapshot_refs

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

    async def _delete_file_versions(self, item: DriveItem) -> tuple[int, set[str]]:
        """Remove a file's ``file_versions`` rows. Returns ``(bytes_freed,
        storage_keys)`` — the bytes the user logically reclaims (for quota) and
        the blob keys that become deletion *candidates*.

        The ``file_versions`` rows must be removed before the ``drive_items`` row
        (FK ``file_versions.file_id`` → ``drive_items.id``), otherwise the
        subsequent hard delete violates the constraint. Blobs themselves are NOT
        deleted here — content is shared with snapshots, so physical reclamation
        is deferred to ``_reclaim_blobs`` (after all metadata is gone) / GC.
        """
        freed = 0
        keys: set[str] = set()
        for version in await self._versions.list_by_file(item.id):
            freed += version.size_bytes
            keys.add(version.storage_key)
        await self._versions.delete_by_file(item.id)
        return freed, keys

    async def _reclaim_blobs(self, storage_keys: set[str]) -> None:
        """Delete blobs that are now fully orphaned. A blob still reachable by a
        snapshot is left in place for GC to reclaim once that snapshot is gone.
        Call only after the owning metadata (versions + items) is deleted."""
        for key in storage_keys:
            if self._snapshot_refs is None:
                # Can't prove the blob is unreferenced → leave it for GC.
                continue
            if await self._snapshot_refs.is_referenced_by_snapshot(key):
                continue
            if await self._storage.exists(key):
                await self._storage.delete(key)

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
        candidate_keys: set[str] = set()

        if item.item_type == ItemType.FILE:
            freed, keys = await self._delete_file_versions(item)
            total_freed += freed
            candidate_keys |= keys
        else:
            descendants = await self._trash.get_children_recursive(item_id)
            for child in descendants:
                if child.item_type == ItemType.FILE:
                    freed, keys = await self._delete_file_versions(child)
                    total_freed += freed
                    candidate_keys |= keys
                await self._shares.delete_by_item(child.id)
                await self._trash.hard_delete(child.id)

        await self._shares.delete_by_item(item_id)
        await self._trash.hard_delete(item_id)

        # Metadata is gone; now reclaim blobs no snapshot still needs.
        await self._reclaim_blobs(candidate_keys)

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
