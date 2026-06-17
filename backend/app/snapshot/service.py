from __future__ import annotations

from typing import Any
from uuid import UUID

from app.drive.schemas import ItemType
from app.models.snapshot import Snapshot, SnapshotEntry
from app.snapshot.repository import AbstractSnapshotRepository

# Snapshot trigger kinds.
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_MANUAL = "manual"
TRIGGER_ASSISTANT = "assistant"
TRIGGER_PRE_RESTORE = "pre_restore"


class SnapshotService:
    """Time Machine — capture and browse point-in-time snapshots of a drive."""

    def __init__(self, *, repo: AbstractSnapshotRepository) -> None:
        self._repo = repo

    async def create(
        self,
        *,
        user_id: UUID,
        trigger: str = TRIGGER_MANUAL,
        label: str = "",
        pinned: bool = False,
    ) -> Snapshot:
        """Capture the user's current drive into a new snapshot.

        Incremental by content: each entry just references the item's existing
        ``storage_key``/checksum, so a snapshot copies no blobs.
        """

        items = await self._repo.list_owner_items(user_id)
        entries: list[dict[str, Any]] = []
        total_bytes = 0
        for item in items:
            is_file = item.item_type == ItemType.FILE
            entries.append(
                {
                    "item_id": item.id,
                    "parent_item_id": item.parent_id,
                    "name": item.name,
                    "item_type": item.item_type,
                    "storage_key": item.storage_key if is_file else None,
                    "checksum_sha256": item.checksum_sha256 if is_file else None,
                    "size_bytes": item.size_bytes if is_file else 0,
                }
            )
            if is_file:
                total_bytes += item.size_bytes
        return await self._repo.create_snapshot(
            user_id=user_id,
            trigger=trigger,
            label=label,
            pinned=pinned or trigger == TRIGGER_PRE_RESTORE,
            item_count=len(entries),
            total_bytes=total_bytes,
            entries=entries,
        )

    async def list_snapshots(self, *, user_id: UUID) -> list[Snapshot]:
        return await self._repo.list_snapshots(user_id)

    async def browse(
        self, *, user_id: UUID, snapshot_id: UUID, parent_item_id: UUID | None
    ) -> list[SnapshotEntry] | None:
        """Read-only listing of one folder level inside a snapshot. Returns None
        if the snapshot doesn't exist / isn't the user's."""

        snapshot = await self._repo.get_snapshot(user_id=user_id, snapshot_id=snapshot_id)
        if snapshot is None:
            return None
        return await self._repo.list_entries(snapshot_id=snapshot_id, parent_item_id=parent_item_id)
