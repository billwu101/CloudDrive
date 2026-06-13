from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.share import Share
from app.models.share_link import ShareLink


class AbstractShareManagementRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        item_id: UUID,
        owner_id: UUID,
        target_user_id: UUID,
        permission: str,
    ) -> Share: ...

    @abstractmethod
    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None: ...

    @abstractmethod
    async def update_permission(self, share_id: UUID, permission: str) -> Share: ...

    @abstractmethod
    async def delete(self, share_id: UUID) -> None: ...

    @abstractmethod
    async def delete_by_item(self, item_id: UUID) -> None: ...

    @abstractmethod
    async def list_shared_with_me(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Share], int]: ...


class AbstractShareLinkRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        item_id: UUID,
        token_hash: str,
        permission: str,
        password_hash: str | None,
        expires_at: datetime | None,
        created_by: UUID,
    ) -> ShareLink: ...

    @abstractmethod
    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None: ...

    @abstractmethod
    async def deactivate(self, link_id: UUID) -> None: ...


class SQLShareManagementRepository(AbstractShareManagementRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        item_id: UUID,
        owner_id: UUID,
        target_user_id: UUID,
        permission: str,
    ) -> Share:
        now = datetime.now(UTC)
        share = Share(
            id=uuid4(),
            item_id=item_id,
            owner_id=owner_id,
            target_user_id=target_user_id,
            permission=permission,
            created_at=now,
            updated_at=now,
        )
        self._session.add(share)
        await self._session.flush()
        return share

    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None:
        result = await self._session.execute(
            select(Share).where(Share.item_id == item_id, Share.target_user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_permission(self, share_id: UUID, permission: str) -> Share:
        result = await self._session.execute(select(Share).where(Share.id == share_id))
        share = result.scalar_one()
        share.permission = permission
        share.updated_at = datetime.now(UTC)
        await self._session.flush()
        return share

    async def delete(self, share_id: UUID) -> None:
        await self._session.execute(delete(Share).where(Share.id == share_id))
        await self._session.flush()

    async def delete_by_item(self, item_id: UUID) -> None:
        await self._session.execute(delete(Share).where(Share.item_id == item_id))
        await self._session.flush()

    async def list_shared_with_me(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Share], int]:
        where = (Share.target_user_id == user_id,)
        count_result = await self._session.execute(select(Share.id).where(*where))
        total = len(count_result.all())
        rows = await self._session.execute(
            select(Share)
            .where(*where)
            .order_by(Share.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(rows.scalars().all()), total


class SQLShareLinkRepository(AbstractShareLinkRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        item_id: UUID,
        token_hash: str,
        permission: str,
        password_hash: str | None,
        expires_at: datetime | None,
        created_by: UUID,
    ) -> ShareLink:
        now = datetime.now(UTC)
        link = ShareLink(
            id=uuid4(),
            item_id=item_id,
            token_hash=token_hash,
            permission=permission,
            password_hash=password_hash,
            expires_at=expires_at,
            is_active=True,
            created_by=created_by,
            created_at=now,
        )
        self._session.add(link)
        await self._session.flush()
        return link

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None:
        result = await self._session.execute(
            select(ShareLink).where(ShareLink.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def deactivate(self, link_id: UUID) -> None:
        result = await self._session.execute(select(ShareLink).where(ShareLink.id == link_id))
        link = result.scalar_one()
        link.is_active = False
        await self._session.flush()
