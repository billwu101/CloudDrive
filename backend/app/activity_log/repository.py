from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_log import ActivityLog


class AbstractActivityLogRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        actor_id: UUID,
        item_id: UUID | None,
        action: str,
        metadata: dict[str, Any],
        ip_address: str | None,
        user_agent: str | None,
    ) -> ActivityLog: ...

    @abstractmethod
    async def list_by_actor(self, actor_id: UUID, *, limit: int = 50) -> list[ActivityLog]: ...

    @abstractmethod
    async def list_by_item(self, item_id: UUID, *, limit: int = 50) -> list[ActivityLog]: ...

    @abstractmethod
    async def get_recent_item_ids(
        self,
        actor_id: UUID,
        *,
        limit: int = 20,
        exclude_item_ids: set[UUID] | None = None,
    ) -> list[UUID]: ...


class SQLActivityLogRepository(AbstractActivityLogRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        actor_id: UUID,
        item_id: UUID | None,
        action: str,
        metadata: dict[str, Any],
        ip_address: str | None,
        user_agent: str | None,
    ) -> ActivityLog:
        log = ActivityLog(
            id=uuid4(),
            actor_id=actor_id,
            item_id=item_id,
            action=action,
            log_metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
        self._session.add(log)
        await self._session.flush()
        return log

    async def list_by_actor(self, actor_id: UUID, *, limit: int = 50) -> list[ActivityLog]:
        result = await self._session.execute(
            select(ActivityLog)
            .where(ActivityLog.actor_id == actor_id)
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_item(self, item_id: UUID, *, limit: int = 50) -> list[ActivityLog]:
        result = await self._session.execute(
            select(ActivityLog)
            .where(ActivityLog.item_id == item_id)
            .order_by(desc(ActivityLog.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_item_ids(
        self,
        actor_id: UUID,
        *,
        limit: int = 20,
        exclude_item_ids: set[UUID] | None = None,
    ) -> list[UUID]:
        subq = (
            select(
                ActivityLog.item_id,
                func.max(ActivityLog.created_at).label("last_activity"),
            )
            .where(
                ActivityLog.actor_id == actor_id,
                ActivityLog.item_id.is_not(None),
            )
            .group_by(ActivityLog.item_id)
            .subquery()
        )
        stmt = select(subq.c.item_id).order_by(desc(subq.c.last_activity)).limit(limit)
        if exclude_item_ids:
            stmt = stmt.where(subq.c.item_id.not_in(exclude_item_ids))
        result = await self._session.execute(stmt)
        return [row[0] for row in result.all() if row[0] is not None]
