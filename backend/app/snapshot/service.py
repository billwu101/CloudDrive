from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
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


@dataclass(frozen=True)
class RestoreOutcome:
    pre_restore_snapshot_id: UUID
    restored: int
    trashed: int


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

    async def restore(
        self,
        *,
        user_id: UUID,
        snapshot_id: UUID,
        scope: str = "whole",
        item_ids: list[UUID] | None = None,
        subtree_mode: str = "keep_new",
    ) -> RestoreOutcome | None:
        """In-place restore the drive (or selected items) to a snapshot.

        Always takes a `pre_restore` safety snapshot first (so the restore is
        itself reversible). Items are upserted by their original id — recreating
        deleted ones and reverting renames/moves/content. `exact_mirror` also
        trashes items added since the snapshot; `keep_new` leaves them.
        Returns None if the snapshot isn't found / isn't the user's.
        """

        snapshot = await self._repo.get_snapshot(user_id=user_id, snapshot_id=snapshot_id)
        if snapshot is None:
            return None

        # 1. Safety snapshot before any mutation.
        pre = await self.create(
            user_id=user_id,
            trigger=TRIGGER_PRE_RESTORE,
            label=f"Before restore of snapshot {snapshot_id}",
        )

        # 2. Which entries to restore.
        all_entries = await self._repo.list_all_entries(snapshot_id)
        if scope == "whole":
            target = all_entries
        else:
            target = _expand_with_descendants(all_entries, set(item_ids or []))

        # 3. Upsert parents before children (drive_items.parent_id is a self-FK).
        restored = 0
        for entry in _parents_first(target):
            await self._repo.upsert_item(owner_id=user_id, entry=entry)
            restored += 1

        # 4. exact_mirror: trash items present now but absent from the snapshot.
        trashed = 0
        if subtree_mode == "exact_mirror":
            entry_ids = {e.item_id for e in all_entries}
            scope_ids = None if scope == "whole" else {e.item_id for e in target}
            for item in await self._repo.list_all_items(user_id):
                if item.is_deleted or item.id in entry_ids:
                    continue
                if scope_ids is not None and item.parent_id not in scope_ids:
                    continue  # only mirror inside the restored subtree
                await self._repo.set_deleted(item_id=item.id, deleted=True)
                trashed += 1

        return RestoreOutcome(pre_restore_snapshot_id=pre.id, restored=restored, trashed=trashed)


def _expand_with_descendants(
    entries: list[SnapshotEntry], selected: set[UUID]
) -> list[SnapshotEntry]:
    by_parent: dict[UUID | None, list[SnapshotEntry]] = defaultdict(list)
    for entry in entries:
        by_parent[entry.parent_item_id].append(entry)
    result: dict[UUID, SnapshotEntry] = {}
    stack = [e for e in entries if e.item_id in selected]
    while stack:
        entry = stack.pop()
        if entry.item_id in result:
            continue
        result[entry.item_id] = entry
        stack.extend(by_parent.get(entry.item_id, []))
    return list(result.values())


def _parents_first(entries: list[SnapshotEntry]) -> list[SnapshotEntry]:
    by_id = {e.item_id: e for e in entries}

    def depth(entry: SnapshotEntry) -> int:
        d = 0
        cur = entry
        seen: set[UUID] = set()
        while cur.parent_item_id in by_id and cur.parent_item_id not in seen:
            seen.add(cur.item_id)
            cur = by_id[cur.parent_item_id]
            d += 1
        return d

    return sorted(entries, key=depth)
