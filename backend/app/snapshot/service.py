from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.drive.schemas import ItemType
from app.models.snapshot import Snapshot, SnapshotEntry, SnapshotSettings
from app.snapshot.repository import AbstractSnapshotRepository
from app.storage.base import StorageProvider

# Snapshot trigger kinds.
TRIGGER_SCHEDULED = "scheduled"
TRIGGER_MANUAL = "manual"
TRIGGER_ASSISTANT = "assistant"
TRIGGER_PRE_RESTORE = "pre_restore"

# Triggers that prune never deletes (safety / user-explicit).
_PRUNE_EXEMPT = frozenset({TRIGGER_PRE_RESTORE})

# Settings defaults (used when a user has never customised them).
DEFAULT_RETENTION_N = 50
DEFAULT_SCHEDULE_INTERVAL_MINUTES = 60


@dataclass(frozen=True)
class RestoreOutcome:
    pre_restore_snapshot_id: UUID
    restored: int
    trashed: int


@dataclass(frozen=True)
class GcOutcome:
    deleted: int
    freed_bytes: int
    skipped_recent: int  # within the grace period, left for a later sweep


class SnapshotService:
    """Time Machine — capture and browse point-in-time snapshots of a drive."""

    def __init__(
        self,
        *,
        repo: AbstractSnapshotRepository,
        activity: Any | None = None,
        storage: StorageProvider | None = None,
    ) -> None:
        self._repo = repo
        # ActivityLogService (optional — swallows its own failures); duck-typed
        # to avoid a hard module dependency.
        self._activity = activity
        # Needed only for blob garbage collection.
        self._storage = storage

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
        ``storage_key``/checksum, so a snapshot copies no blobs. After creating,
        old snapshots are pruned to honour retention-N and the snapshot quota.
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
        snapshot = await self._repo.create_snapshot(
            user_id=user_id,
            trigger=trigger,
            label=label,
            pinned=pinned or trigger == TRIGGER_PRE_RESTORE,
            item_count=len(entries),
            total_bytes=total_bytes,
            entries=entries,
        )
        await self.prune(user_id=user_id)
        return snapshot

    async def list_snapshots(self, *, user_id: UUID) -> list[Snapshot]:
        return await self._repo.list_snapshots(user_id)

    async def used_bytes(self, *, user_id: UUID) -> int:
        return await self._repo.used_snapshot_bytes(user_id)

    # ----- settings -------------------------------------------------------

    async def get_settings(self, *, user_id: UUID) -> SnapshotSettings:
        """Effective settings; returns a transient default if never customised."""

        settings = await self._repo.get_settings(user_id)
        if settings is None:
            settings = SnapshotSettings(
                user_id=user_id,
                retention_n=DEFAULT_RETENTION_N,
                schedule_enabled=True,
                schedule_interval_minutes=DEFAULT_SCHEDULE_INTERVAL_MINUTES,
                quota_bytes=None,
            )
        return settings

    async def resolve_quota_bytes(
        self, *, user_id: UUID, settings: SnapshotSettings | None = None
    ) -> int:
        """The effective snapshot quota in bytes. ``quota_bytes=None`` means auto
        — half the user's overall file quota."""

        settings = settings or await self.get_settings(user_id=user_id)
        if settings.quota_bytes is not None:
            return settings.quota_bytes
        return await self._repo.get_user_quota_bytes(user_id) // 2

    async def update_settings(
        self,
        *,
        user_id: UUID,
        retention_n: int,
        schedule_enabled: bool,
        schedule_interval_minutes: int,
        quota_bytes: int | None,
    ) -> SnapshotSettings:
        retention_n = max(1, retention_n)
        schedule_interval_minutes = max(1, schedule_interval_minutes)
        if quota_bytes is not None:
            quota_bytes = max(0, quota_bytes)
        settings = await self._repo.upsert_settings(
            user_id=user_id,
            retention_n=retention_n,
            schedule_enabled=schedule_enabled,
            schedule_interval_minutes=schedule_interval_minutes,
            quota_bytes=quota_bytes,
        )
        # Apply tightened retention/quota right away.
        await self.prune(user_id=user_id, settings=settings)
        return settings

    # ----- retention / quota ---------------------------------------------

    async def prune(self, *, user_id: UUID, settings: SnapshotSettings | None = None) -> int:
        """Delete old snapshots beyond retention-N and over the quota.

        Never deletes the newest snapshot, pinned snapshots, or pre_restore
        safety snapshots. Returns the number deleted.
        """

        settings = settings or await self.get_settings(user_id=user_id)
        snaps = await self._repo.list_snapshots(user_id)  # newest first
        deleted = 0

        def _exempt(s: Snapshot) -> bool:
            return s.pinned or s.trigger in _PRUNE_EXEMPT

        # Retention: keep the newest N; anything older that isn't exempt goes.
        kept_ids: set[UUID] = set()
        for i, s in enumerate(snaps):
            if i < settings.retention_n or _exempt(s):
                kept_ids.add(s.id)
                continue
            await self._repo.delete_snapshot(s.id)
            deleted += 1

        # Quota: drop oldest non-exempt survivors until under the cap. Always
        # keep the newest snapshot regardless.
        quota = await self.resolve_quota_bytes(user_id=user_id, settings=settings)
        if quota > 0 and snaps:
            newest_id = snaps[0].id
            survivors = [s for s in snaps if s.id in kept_ids]
            for s in reversed(survivors):  # oldest first
                if s.id == newest_id or _exempt(s):
                    continue
                if await self._repo.used_snapshot_bytes(user_id) <= quota:
                    break
                await self._repo.delete_snapshot(s.id)
                deleted += 1

        return deleted

    # ----- scheduling -----------------------------------------------------

    async def run_scheduled_snapshot(
        self, *, user_id: UUID, now: datetime | None = None
    ) -> Snapshot | None:
        """Create a `scheduled` snapshot if one is due.

        Due means: schedule enabled, the interval has elapsed since the last
        snapshot of any kind, and the drive currently has at least one item
        (so empty/idle drives don't accumulate identical empty snapshots).
        Returns the snapshot if created, else None.
        """

        settings = await self.get_settings(user_id=user_id)
        if not settings.schedule_enabled:
            return None

        now = now or datetime.now(UTC)
        snaps = await self._repo.list_snapshots(user_id)  # newest first
        if snaps:
            last = snaps[0].created_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if now - last < timedelta(minutes=settings.schedule_interval_minutes):
                return None

        items = await self._repo.list_owner_items(user_id)
        if not items:
            return None

        return await self.create(user_id=user_id, trigger=TRIGGER_SCHEDULED, label="Scheduled")

    # ----- blob garbage collection ---------------------------------------

    async def collect_garbage(
        self, *, grace_minutes: int = 60, now: datetime | None = None
    ) -> GcOutcome:
        """Reclaim content blobs no longer referenced by any live item, file
        version, or snapshot entry.

        Snapshots and items are content-addressed: deleting a snapshot or item
        only removes metadata, leaving the underlying blob in place because other
        snapshots/items may still reference it. This sweep computes the live set
        of ``storage_key``s across all reference sources and deletes any stored
        blob outside it.

        A ``grace_minutes`` window protects blobs written very recently (e.g. an
        upload whose DB row isn't committed/visible yet at sweep time) from being
        mistaken for orphans. This is a cross-user, global operation.
        """

        if self._storage is None:
            raise RuntimeError("collect_garbage requires a storage provider")

        referenced = await self._repo.referenced_storage_keys()
        cutoff = (now or datetime.now(UTC)).timestamp() - grace_minutes * 60

        deleted = 0
        freed_bytes = 0
        skipped_recent = 0
        for blob in await self._storage.list_objects():
            if blob.key in referenced:
                continue
            if blob.modified_at >= cutoff:
                skipped_recent += 1  # too new to be sure it's an orphan
                continue
            await self._storage.delete(blob.key)
            deleted += 1
            freed_bytes += blob.size

        return GcOutcome(deleted=deleted, freed_bytes=freed_bytes, skipped_recent=skipped_recent)

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

        if self._activity is not None:
            await self._activity.log(
                actor_id=user_id,
                action="snapshot.restore",
                metadata={
                    "snapshot_id": str(snapshot_id),
                    "pre_restore_snapshot_id": str(pre.id),
                    "scope": scope,
                    "subtree_mode": subtree_mode,
                    "restored": restored,
                    "trashed": trashed,
                },
            )

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
