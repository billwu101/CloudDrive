from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.external_model_connection import ExternalModelConnection


class AbstractConnectionRepository(ABC):
    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[ExternalModelConnection]: ...

    @abstractmethod
    async def get(self, user_id: UUID, connection_id: UUID) -> ExternalModelConnection | None: ...

    @abstractmethod
    async def create(self, connection: ExternalModelConnection) -> ExternalModelConnection: ...

    @abstractmethod
    async def update(
        self,
        *,
        user_id: UUID,
        connection_id: UUID,
        label: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        secret_encrypted: str | None = None,
        masked_hint: str | None = None,
        status: str | None = None,
        updated_at: datetime,
    ) -> ExternalModelConnection | None: ...

    @abstractmethod
    async def delete(self, user_id: UUID, connection_id: UUID) -> bool: ...

    @abstractmethod
    async def set_status(self, user_id: UUID, connection_id: UUID, status: str) -> None: ...


class SQLConnectionRepository(AbstractConnectionRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: UUID) -> list[ExternalModelConnection]:
        result = await self._session.execute(
            select(ExternalModelConnection)
            .where(ExternalModelConnection.user_id == user_id)
            .order_by(ExternalModelConnection.created_at.asc())
        )
        return list(result.scalars().all())

    async def get(self, user_id: UUID, connection_id: UUID) -> ExternalModelConnection | None:
        result = await self._session.execute(
            select(ExternalModelConnection).where(
                ExternalModelConnection.user_id == user_id,
                ExternalModelConnection.id == connection_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(self, connection: ExternalModelConnection) -> ExternalModelConnection:
        self._session.add(connection)
        await self._session.flush()
        return connection

    async def update(
        self,
        *,
        user_id: UUID,
        connection_id: UUID,
        label: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        secret_encrypted: str | None = None,
        masked_hint: str | None = None,
        status: str | None = None,
        updated_at: datetime,
    ) -> ExternalModelConnection | None:
        conn = await self.get(user_id, connection_id)
        if conn is None:
            return None
        if label is not None:
            conn.label = label
        if base_url is not None:
            conn.base_url = base_url
        if model is not None:
            conn.model = model
        if secret_encrypted is not None:
            conn.secret_encrypted = secret_encrypted
        if masked_hint is not None:
            conn.masked_hint = masked_hint
        if status is not None:
            conn.status = status
        conn.updated_at = updated_at
        await self._session.flush()
        return conn

    async def delete(self, user_id: UUID, connection_id: UUID) -> bool:
        conn = await self.get(user_id, connection_id)
        if conn is None:
            return False
        await self._session.delete(conn)
        await self._session.flush()
        return True

    async def set_status(self, user_id: UUID, connection_id: UUID, status: str) -> None:
        conn = await self.get(user_id, connection_id)
        if conn is not None:
            conn.status = status
            await self._session.flush()
