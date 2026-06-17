from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.drive.schemas import ItemType
from app.models.drive_item import DriveItem
from app.models.snapshot import Snapshot, SnapshotEntry
from app.snapshot.repository import AbstractSnapshotRepository
from app.snapshot.service import TRIGGER_MANUAL, TRIGGER_PRE_RESTORE, SnapshotService


def _item(
    owner: UUID,
    *,
    item_type: ItemType = ItemType.FILE,
    name: str = "f.txt",
    parent_id: UUID | None = None,
    size: int = 100,
) -> DriveItem:
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=owner,
        parent_id=parent_id,
        item_type=item_type,
        name=name,
        mime_type="text/plain",
        extension="txt",
        size_bytes=size,
        storage_key=f"k/{name}" if item_type == ItemType.FILE else None,
        checksum_sha256="abc" if item_type == ItemType.FILE else None,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


class MemSnapshotRepo(AbstractSnapshotRepository):
    def __init__(self, items: list[DriveItem]) -> None:
        self.items: dict[UUID, DriveItem] = {i.id: i for i in items}
        self.snapshots: dict[UUID, Snapshot] = {}
        self.entries: dict[UUID, list[SnapshotEntry]] = {}

    async def list_owner_items(self, owner_id: UUID) -> list[DriveItem]:
        return [i for i in self.items.values() if i.owner_id == owner_id and not i.is_deleted]

    async def list_all_entries(self, snapshot_id: UUID) -> list[SnapshotEntry]:
        return list(self.entries.get(snapshot_id, []))

    async def list_all_items(self, owner_id: UUID) -> list[DriveItem]:
        return [i for i in self.items.values() if i.owner_id == owner_id]

    async def upsert_item(self, *, owner_id: UUID, entry: SnapshotEntry) -> None:
        existing = self.items.get(entry.item_id)
        if existing is None:
            self.items[entry.item_id] = _item(
                owner_id,
                item_type=ItemType(entry.item_type),
                name=entry.name,
                parent_id=entry.parent_item_id,
                size=entry.size_bytes,
            )
            self.items[entry.item_id].id = entry.item_id
        else:
            existing.name = entry.name
            existing.parent_id = entry.parent_item_id
            existing.size_bytes = entry.size_bytes
            existing.storage_key = entry.storage_key
            existing.is_deleted = False

    async def set_deleted(self, *, item_id: UUID, deleted: bool) -> None:
        if item_id in self.items:
            self.items[item_id].is_deleted = deleted

    async def create_snapshot(
        self,
        *,
        user_id: UUID,
        trigger: str,
        label: str,
        pinned: bool,
        item_count: int,
        total_bytes: int,
        entries: list[dict[str, Any]],
    ) -> Snapshot:
        snap = Snapshot(
            id=uuid4(),
            user_id=user_id,
            trigger=trigger,
            label=label,
            pinned=pinned,
            item_count=item_count,
            total_bytes=total_bytes,
            created_at=datetime.now(UTC),
        )
        self.snapshots[snap.id] = snap
        self.entries[snap.id] = [
            SnapshotEntry(id=uuid4(), snapshot_id=snap.id, **e) for e in entries
        ]
        return snap

    async def list_snapshots(self, user_id: UUID) -> list[Snapshot]:
        return [s for s in self.snapshots.values() if s.user_id == user_id]

    async def get_snapshot(self, *, user_id: UUID, snapshot_id: UUID) -> Snapshot | None:
        snap = self.snapshots.get(snapshot_id)
        return snap if snap and snap.user_id == user_id else None

    async def list_entries(
        self, *, snapshot_id: UUID, parent_item_id: UUID | None
    ) -> list[SnapshotEntry]:
        return [e for e in self.entries.get(snapshot_id, []) if e.parent_item_id == parent_item_id]


async def test_create_captures_current_items_with_counts() -> None:
    user = uuid4()
    folder = _item(user, item_type=ItemType.FOLDER, name="docs")
    f1 = _item(user, name="a.txt", parent_id=folder.id, size=100)
    f2 = _item(user, name="b.txt", parent_id=folder.id, size=250)
    repo = MemSnapshotRepo([folder, f1, f2])
    svc = SnapshotService(repo=repo)

    snap = await svc.create(user_id=user, trigger=TRIGGER_MANUAL, label="manual")

    assert snap.item_count == 3
    assert snap.total_bytes == 350  # folders contribute 0
    assert snap.trigger == "manual"
    entries = repo.entries[snap.id]
    file_entry = next(e for e in entries if e.name == "a.txt")
    assert file_entry.storage_key == "k/a.txt"  # content pointer captured
    assert file_entry.parent_item_id == folder.id


async def test_pre_restore_trigger_is_pinned() -> None:
    user = uuid4()
    repo = MemSnapshotRepo([_item(user)])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user, trigger=TRIGGER_PRE_RESTORE)
    assert snap.pinned is True  # safety snapshots are never auto-pruned


async def test_browse_lists_one_level() -> None:
    user = uuid4()
    folder = _item(user, item_type=ItemType.FOLDER, name="docs")
    child = _item(user, name="a.txt", parent_id=folder.id)
    root_file = _item(user, name="root.txt")
    repo = MemSnapshotRepo([folder, child, root_file])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user)

    root = await svc.browse(user_id=user, snapshot_id=snap.id, parent_item_id=None)
    assert root is not None
    assert {e.name for e in root} == {"docs", "root.txt"}

    inside = await svc.browse(user_id=user, snapshot_id=snap.id, parent_item_id=folder.id)
    assert inside is not None
    assert {e.name for e in inside} == {"a.txt"}


async def test_browse_unknown_snapshot_returns_none() -> None:
    user = uuid4()
    svc = SnapshotService(repo=MemSnapshotRepo([_item(user)]))
    assert await svc.browse(user_id=user, snapshot_id=uuid4(), parent_item_id=None) is None


async def test_browse_other_users_snapshot_returns_none() -> None:
    owner, other = uuid4(), uuid4()
    repo = MemSnapshotRepo([_item(owner)])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=owner)
    assert await svc.browse(user_id=other, snapshot_id=snap.id, parent_item_id=None) is None


# ── restore ──────────────────────────────────────────────────────────────────


async def test_restore_takes_pre_restore_snapshot_first() -> None:
    user = uuid4()
    repo = MemSnapshotRepo([_item(user, name="a.txt")])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user)

    outcome = await svc.restore(user_id=user, snapshot_id=snap.id)

    assert outcome is not None
    pre = repo.snapshots[outcome.pre_restore_snapshot_id]
    assert pre.trigger == "pre_restore"
    assert pre.pinned is True


async def test_restore_recreates_a_deleted_item() -> None:
    user = uuid4()
    f = _item(user, name="keep.txt")
    repo = MemSnapshotRepo([f])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user)
    # user hard-deletes the file after the snapshot
    del repo.items[f.id]

    outcome = await svc.restore(user_id=user, snapshot_id=snap.id)

    assert outcome is not None and outcome.restored == 1
    assert f.id in repo.items  # recreated with its original id
    assert repo.items[f.id].name == "keep.txt"
    assert repo.items[f.id].is_deleted is False


async def test_restore_reverts_a_rename() -> None:
    user = uuid4()
    f = _item(user, name="original.txt")
    repo = MemSnapshotRepo([f])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user)
    repo.items[f.id].name = "renamed.txt"  # changed after snapshot

    await svc.restore(user_id=user, snapshot_id=snap.id)

    assert repo.items[f.id].name == "original.txt"


async def test_restore_exact_mirror_trashes_new_item_keep_new_does_not() -> None:
    user = uuid4()
    original = _item(user, name="original.txt")
    repo = MemSnapshotRepo([original])
    svc = SnapshotService(repo=repo)
    snap = await svc.create(user_id=user)
    # a new file added after the snapshot
    added = _item(user, name="added.txt")
    repo.items[added.id] = added

    keep = await svc.restore(user_id=user, snapshot_id=snap.id, subtree_mode="keep_new")
    assert keep is not None and keep.trashed == 0
    assert repo.items[added.id].is_deleted is False

    mirror = await svc.restore(user_id=user, snapshot_id=snap.id, subtree_mode="exact_mirror")
    assert mirror is not None and mirror.trashed == 1
    assert repo.items[added.id].is_deleted is True


async def test_restore_unknown_snapshot_returns_none() -> None:
    user = uuid4()
    svc = SnapshotService(repo=MemSnapshotRepo([_item(user)]))
    assert await svc.restore(user_id=user, snapshot_id=uuid4()) is None
