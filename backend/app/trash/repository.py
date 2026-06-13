from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem


class AbstractTrashRepository(ABC):
    @abstractmethod
    async def mark_deleted(self, item_id: UUID, deleted_at: datetime) -> DriveItem: ...

    @abstractmethod
    async def mark_restored(self, item_id: UUID) -> DriveItem: ...

    @abstractmethod
    async def list_deleted(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[DriveItem], int]: ...

    @abstractmethod
    async def get_all_deleted(self, owner_id: UUID) -> list[DriveItem]: ...

    @abstractmethod
    async def hard_delete(self, item_id: UUID) -> None: ...

    @abstractmethod
    async def get_children_recursive(self, item_id: UUID) -> list[DriveItem]: ...


class SQLTrashRepository(AbstractTrashRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _get(self, item_id: UUID) -> DriveItem:
        result = await self._session.execute(select(DriveItem).where(DriveItem.id == item_id))
        return result.scalar_one()

    async def mark_deleted(self, item_id: UUID, deleted_at: datetime) -> DriveItem:
        item = await self._get(item_id)
        item.is_deleted = True
        item.deleted_at = deleted_at
        item.updated_at = datetime.now(UTC)
        await self._session.flush()
        return item

    async def mark_restored(self, item_id: UUID) -> DriveItem:
        item = await self._get(item_id)
        item.is_deleted = False
        item.deleted_at = None
        item.updated_at = datetime.now(UTC)
        await self._session.flush()
        return item

    async def list_deleted(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[DriveItem], int]:
        where = (DriveItem.owner_id == owner_id, DriveItem.is_deleted.is_(True))
        count_result = await self._session.execute(select(DriveItem.id).where(*where))
        total = len(count_result.all())
        rows = await self._session.execute(
            select(DriveItem)
            .where(*where)
            .order_by(DriveItem.deleted_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total

    async def get_all_deleted(self, owner_id: UUID) -> list[DriveItem]:
        result = await self._session.execute(
            select(DriveItem).where(DriveItem.owner_id == owner_id, DriveItem.is_deleted.is_(True))
        )
        return list(result.scalars().all())

    async def hard_delete(self, item_id: UUID) -> None:
        await self._session.execute(delete(DriveItem).where(DriveItem.id == item_id))
        await self._session.flush()

    async def get_children_recursive(self, item_id: UUID) -> list[DriveItem]:
        result: list[DriveItem] = []
        queue = [item_id]
        while queue:
            rows = await self._session.execute(
                select(DriveItem).where(DriveItem.parent_id.in_(queue))
            )
            children = list(rows.scalars().all())
            result.extend(children)
            queue = [c.id for c in children]
        return result
