from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.share import Share


class AbstractShareRepository(ABC):
    @abstractmethod
    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None: ...

    @abstractmethod
    async def delete_by_item(self, item_id: UUID) -> None: ...


class SQLShareRepository(AbstractShareRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None:
        result = await self._session.execute(
            select(Share).where(
                Share.item_id == item_id,
                Share.target_user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def delete_by_item(self, item_id: UUID) -> None:
        await self._session.execute(delete(Share).where(Share.item_id == item_id))
        await self._session.flush()
