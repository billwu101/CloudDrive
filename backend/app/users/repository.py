from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.file_version import FileVersion
from app.models.user import User


class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def update_username(self, user_id: UUID, username: str) -> User: ...

    @abstractmethod
    async def update_email(self, user_id: UUID, email: str) -> User: ...

    @abstractmethod
    async def update_password(self, user_id: UUID, password_hash: str) -> User: ...

    @abstractmethod
    async def add_used_bytes(self, user_id: UUID, delta: int) -> None: ...

    @abstractmethod
    async def subtract_used_bytes(self, user_id: UUID, delta: int) -> None: ...

    @abstractmethod
    async def recalculate_used_bytes(self, user_id: UUID) -> int: ...


class SQLUserRepository(AbstractUserRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def update_username(self, user_id: UUID, username: str) -> User:
        now = datetime.now(UTC)
        await self._session.execute(
            update(User).where(User.id == user_id).values(username=username, updated_at=now)
        )
        await self._session.flush()
        user = await self.get_by_id(user_id)
        assert user is not None
        return user

    async def update_email(self, user_id: UUID, email: str) -> User:
        now = datetime.now(UTC)
        await self._session.execute(
            update(User).where(User.id == user_id).values(email=email, updated_at=now)
        )
        await self._session.flush()
        user = await self.get_by_id(user_id)
        assert user is not None
        return user

    async def update_password(self, user_id: UUID, password_hash: str) -> User:
        now = datetime.now(UTC)
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                password_hash=password_hash,
                must_change_password=False,
                updated_at=now,
            )
        )
        await self._session.flush()
        user = await self.get_by_id(user_id)
        assert user is not None
        return user

    async def add_used_bytes(self, user_id: UUID, delta: int) -> None:
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(used_bytes=User.used_bytes + delta, updated_at=datetime.now(UTC))
        )
        await self._session.flush()

    async def subtract_used_bytes(self, user_id: UUID, delta: int) -> None:
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                used_bytes=func.greatest(0, User.used_bytes - delta),
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.flush()

    async def recalculate_used_bytes(self, user_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.sum(FileVersion.size_bytes), 0)).where(
                FileVersion.file_id.in_(
                    select(DriveItem.id).where(
                        DriveItem.owner_id == user_id,
                        DriveItem.is_deleted.is_(False),
                    )
                )
            )
        )
        total: int = result.scalar_one()
        await self._session.execute(
            update(User)
            .where(User.id == user_id)
            .values(used_bytes=total, updated_at=datetime.now(UTC))
        )
        await self._session.flush()
        return total
