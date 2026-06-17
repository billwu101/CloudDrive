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
        self._items = items
        self.snapshots: dict[UUID, Snapshot] = {}
        self.entries: dict[UUID, list[SnapshotEntry]] = {}

    async def list_owner_items(self, owner_id: UUID) -> list[DriveItem]:
        return [i for i in self._items if i.owner_id == owner_id]

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
