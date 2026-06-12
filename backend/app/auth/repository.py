from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.models.user import User


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class AbstractUserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def create(
        self,
        *,
        email: str,
        username: str,
        password_hash: str,
        quota_bytes: int,
    ) -> User: ...


class SQLUserRepository(AbstractUserRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        result = await self._session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        username: str,
        password_hash: str,
        quota_bytes: int,
    ) -> User:
        now = datetime.now(UTC)
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            password_hash=password_hash,
            quota_bytes=quota_bytes,
            used_bytes=0,
            is_active=True,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self._session.add(user)
        await self._session.flush()
        return user


class AbstractRefreshTokenRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken: ...

    @abstractmethod
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def revoke(self, token_id: UUID) -> None: ...


class SQLRefreshTokenRepository(AbstractRefreshTokenRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        now = datetime.now(UTC)
        rt = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
        )
        self._session.add(rt)
        await self._session.flush()
        return rt

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def revoke(self, token_id: UUID) -> None:
        result = await self._session.execute(
            select(RefreshToken).where(RefreshToken.id == token_id)
        )
        rt = result.scalar_one_or_none()
        if rt is not None:
            rt.revoked_at = datetime.now(UTC)
            await self._session.flush()
