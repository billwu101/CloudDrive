from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user_external_credential import UserExternalCredential


class AbstractExternalCredentialRepository(ABC):
    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[UserExternalCredential]: ...

    @abstractmethod
    async def get(self, user_id: UUID, provider: str) -> UserExternalCredential | None: ...

    @abstractmethod
    async def upsert(
        self,
        *,
        user_id: UUID,
        provider: str,
        auth_type: str,
        secret_encrypted: str,
        masked_hint: str,
        updated_at: datetime,
    ) -> None: ...

    @abstractmethod
    async def delete(self, user_id: UUID, provider: str) -> None: ...

    @abstractmethod
    async def set_status(self, user_id: UUID, provider: str, status: str) -> None: ...


class SQLExternalCredentialRepository(AbstractExternalCredentialRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_user(self, user_id: UUID) -> list[UserExternalCredential]:
        result = await self._session.execute(
            select(UserExternalCredential).where(UserExternalCredential.user_id == user_id)
        )
        return list(result.scalars().all())

    async def get(self, user_id: UUID, provider: str) -> UserExternalCredential | None:
        result = await self._session.execute(
            select(UserExternalCredential).where(
                UserExternalCredential.user_id == user_id,
                UserExternalCredential.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        user_id: UUID,
        provider: str,
        auth_type: str,
        secret_encrypted: str,
        masked_hint: str,
        updated_at: datetime,
    ) -> None:
        values = {
            "user_id": user_id,
            "provider": provider,
            "auth_type": auth_type,
            "secret_encrypted": secret_encrypted,
            "masked_hint": masked_hint,
            "status": "active",
            "updated_at": updated_at,
        }
        stmt = pg_insert(UserExternalCredential).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                UserExternalCredential.user_id,
                UserExternalCredential.provider,
            ],
            set_={
                "auth_type": auth_type,
                "secret_encrypted": secret_encrypted,
                "masked_hint": masked_hint,
                "status": "active",
                "updated_at": updated_at,
            },
        )
        await self._session.execute(stmt)

    async def delete(self, user_id: UUID, provider: str) -> None:
        await self._session.execute(
            delete(UserExternalCredential).where(
                UserExternalCredential.user_id == user_id,
                UserExternalCredential.provider == provider,
            )
        )

    async def set_status(self, user_id: UUID, provider: str, status: str) -> None:
        await self._session.execute(
            update(UserExternalCredential)
            .where(
                UserExternalCredential.user_id == user_id,
                UserExternalCredential.provider == provider,
            )
            .values(status=status)
        )
