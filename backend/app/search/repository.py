from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.share import Share


class AbstractSearchRepository(ABC):
    @abstractmethod
    async def search(
        self,
        user_id: UUID,
        query: str,
        *,
        item_type: str | None = None,
        mime_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DriveItem], int]: ...


class SQLSearchRepository(AbstractSearchRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(
        self,
        user_id: UUID,
        query: str,
        *,
        item_type: str | None = None,
        mime_type: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[DriveItem], int]:
        # Items owned by user OR items shared with user
        shared_subq = select(Share.item_id).where(Share.target_user_id == user_id)
        base_where = [
            DriveItem.is_deleted.is_(False),
            DriveItem.name.ilike(f"%{query}%"),
            or_(DriveItem.owner_id == user_id, DriveItem.id.in_(shared_subq)),
        ]
        if item_type is not None:
            base_where.append(DriveItem.item_type == item_type)
        if mime_type is not None:
            base_where.append(DriveItem.mime_type == mime_type)

        count_result = await self._session.execute(select(DriveItem.id).where(*base_where))
        total = len(count_result.all())

        rows = await self._session.execute(
            select(DriveItem)
            .where(*base_where)
            .order_by(DriveItem.name)
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total
