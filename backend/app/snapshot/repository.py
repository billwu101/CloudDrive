from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.snapshot import Snapshot, SnapshotEntry


class AbstractSnapshotRepository(ABC):
    @abstractmethod
    async def list_owner_items(self, owner_id: UUID) -> list[DriveItem]:
        """Current (non-deleted) drive items for the owner — the snapshot source."""

    @abstractmethod
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
    ) -> Snapshot: ...

    @abstractmethod
    async def list_snapshots(self, user_id: UUID) -> list[Snapshot]: ...

    @abstractmethod
    async def get_snapshot(self, *, user_id: UUID, snapshot_id: UUID) -> Snapshot | None: ...

    @abstractmethod
    async def list_entries(
        self, *, snapshot_id: UUID, parent_item_id: UUID | None
    ) -> list[SnapshotEntry]: ...

    @abstractmethod
    async def list_all_entries(self, snapshot_id: UUID) -> list[SnapshotEntry]: ...

    @abstractmethod
    async def list_all_items(self, owner_id: UUID) -> list[DriveItem]:
        """Every drive item for the owner, INCLUDING deleted — for restore diffing."""

    @abstractmethod
    async def upsert_item(self, *, owner_id: UUID, entry: SnapshotEntry) -> None:
        """Recreate (with the original id) or update a drive item to match a
        snapshot entry, clearing is_deleted. Reusing the original id keeps parent
        references consistent without remapping."""

    @abstractmethod
    async def set_deleted(self, *, item_id: UUID, deleted: bool) -> None: ...


class SQLSnapshotRepository(AbstractSnapshotRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_owner_items(self, owner_id: UUID) -> list[DriveItem]:
        result = await self._session.execute(
            select(DriveItem).where(
                DriveItem.owner_id == owner_id,
                DriveItem.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())

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
        snapshot = Snapshot(
            id=uuid4(),
            user_id=user_id,
            trigger=trigger,
            label=label,
            pinned=pinned,
            item_count=item_count,
            total_bytes=total_bytes,
            created_at=datetime.now(UTC),
        )
        self._session.add(snapshot)
        await self._session.flush()
        for entry in entries:
            self._session.add(SnapshotEntry(id=uuid4(), snapshot_id=snapshot.id, **entry))
        await self._session.flush()
        return snapshot

    async def list_snapshots(self, user_id: UUID) -> list[Snapshot]:
        result = await self._session.execute(
            select(Snapshot).where(Snapshot.user_id == user_id).order_by(Snapshot.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_snapshot(self, *, user_id: UUID, snapshot_id: UUID) -> Snapshot | None:
        result = await self._session.execute(
            select(Snapshot).where(Snapshot.id == snapshot_id, Snapshot.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_entries(
        self, *, snapshot_id: UUID, parent_item_id: UUID | None
    ) -> list[SnapshotEntry]:
        stmt = select(SnapshotEntry).where(SnapshotEntry.snapshot_id == snapshot_id)
        if parent_item_id is None:
            stmt = stmt.where(SnapshotEntry.parent_item_id.is_(None))
        else:
            stmt = stmt.where(SnapshotEntry.parent_item_id == parent_item_id)
        result = await self._session.execute(stmt.order_by(SnapshotEntry.name))
        return list(result.scalars().all())

    async def list_all_entries(self, snapshot_id: UUID) -> list[SnapshotEntry]:
        result = await self._session.execute(
            select(SnapshotEntry).where(SnapshotEntry.snapshot_id == snapshot_id)
        )
        return list(result.scalars().all())

    async def list_all_items(self, owner_id: UUID) -> list[DriveItem]:
        result = await self._session.execute(
            select(DriveItem).where(DriveItem.owner_id == owner_id)
        )
        return list(result.scalars().all())

    async def upsert_item(self, *, owner_id: UUID, entry: SnapshotEntry) -> None:
        now = datetime.now(UTC)
        existing = (
            await self._session.execute(select(DriveItem).where(DriveItem.id == entry.item_id))
        ).scalar_one_or_none()
        if existing is None:
            self._session.add(
                DriveItem(
                    id=entry.item_id,
                    owner_id=owner_id,
                    parent_id=entry.parent_item_id,
                    item_type=entry.item_type,
                    name=entry.name,
                    size_bytes=entry.size_bytes,
                    storage_key=entry.storage_key,
                    checksum_sha256=entry.checksum_sha256,
                    is_starred=False,
                    is_deleted=False,
                    created_by=owner_id,
                    updated_by=owner_id,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            existing.parent_id = entry.parent_item_id
            existing.name = entry.name
            existing.size_bytes = entry.size_bytes
            existing.storage_key = entry.storage_key
            existing.checksum_sha256 = entry.checksum_sha256
            existing.is_deleted = False
            existing.deleted_at = None
            existing.updated_at = now
        await self._session.flush()

    async def set_deleted(self, *, item_id: UUID, deleted: bool) -> None:
        item = (
            await self._session.execute(select(DriveItem).where(DriveItem.id == item_id))
        ).scalar_one_or_none()
        if item is not None:
            item.is_deleted = deleted
            item.deleted_at = datetime.now(UTC) if deleted else None
            await self._session.flush()
