from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.share import Share
from app.models.share_link import ShareLink
from app.models.user import User


@dataclass
class SharedByMeRow:
    """One shared item plus every share record attached to it."""

    item: DriveItem
    shares: list[tuple[Share, User]]
    links: list[ShareLink]


@dataclass(frozen=True)
class ShareBadges:
    """Whether an item is shared with people, publicly linked, or both."""

    shared_with_users: bool
    has_active_public_link: bool


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

    @abstractmethod
    async def list_shared_by_me(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[SharedByMeRow], int]:
        """Items this owner has shared out, one row per item (proposal §29).

        Trashed items are excluded; disabled/expired links are kept so the
        owner can still see a link once existed.
        """

    @abstractmethod
    async def get_share_badges(
        self, owner_id: UUID, item_ids: list[UUID]
    ) -> dict[UUID, ShareBadges]:
        """Sharing state for a page of items, in one round trip.

        Answers "is this shared, and is it public?" for a whole listing at
        once — per-row queries would put an N+1 on the drive's hottest path.
        """


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
    async def get_by_id(self, link_id: UUID) -> ShareLink | None: ...

    @abstractmethod
    async def update_attempt_state(
        self,
        link_id: UUID,
        *,
        window_start: datetime | None,
        count: int,
        locked_until: datetime | None,
    ) -> None:
        """Persist validation-attempt throttling state (design §6.12.11 rule 6)."""

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

    async def _shared_item_ids(self, owner_id: UUID) -> list[UUID]:
        """Ids of this owner's live items that carry any share at all."""
        shared = select(Share.item_id).where(Share.owner_id == owner_id)
        linked = select(ShareLink.item_id).where(ShareLink.created_by == owner_id)
        result = await self._session.execute(
            select(DriveItem.id)
            .where(
                DriveItem.owner_id == owner_id,
                ~DriveItem.is_deleted,
                or_(DriveItem.id.in_(shared), DriveItem.id.in_(linked)),
            )
            .order_by(DriveItem.name)
        )
        return list(result.scalars().all())

    async def list_shared_by_me(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[SharedByMeRow], int]:
        ids = await self._shared_item_ids(owner_id)
        total = len(ids)
        page_ids = ids[offset : offset + limit]
        if not page_ids:
            return [], total

        items = (
            (await self._session.execute(select(DriveItem).where(DriveItem.id.in_(page_ids))))
            .scalars()
            .all()
        )
        share_rows = (
            await self._session.execute(
                select(Share, User)
                .join(User, User.id == Share.target_user_id)
                .where(Share.item_id.in_(page_ids))
                .order_by(Share.created_at)
            )
        ).all()
        link_rows = (
            (
                await self._session.execute(
                    select(ShareLink)
                    .where(ShareLink.item_id.in_(page_ids))
                    .order_by(ShareLink.created_at)
                )
            )
            .scalars()
            .all()
        )

        by_item = {i.id: i for i in items}
        rows = [SharedByMeRow(item=by_item[i], shares=[], links=[]) for i in page_ids]
        index = {r.item.id: r for r in rows}
        for share, user in share_rows:
            index[share.item_id].shares.append((share, user))
        for link in link_rows:
            index[link.item_id].links.append(link)
        return rows, total

    async def get_share_badges(
        self, owner_id: UUID, item_ids: list[UUID]
    ) -> dict[UUID, ShareBadges]:
        if not item_ids:
            return {}
        now = datetime.now(UTC)
        shared = set(
            (
                await self._session.execute(
                    select(Share.item_id).where(
                        Share.owner_id == owner_id, Share.item_id.in_(item_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        linked = set(
            (
                await self._session.execute(
                    select(ShareLink.item_id).where(
                        ShareLink.created_by == owner_id,
                        ShareLink.item_id.in_(item_ids),
                        ShareLink.is_active,
                        or_(ShareLink.expires_at.is_(None), ShareLink.expires_at > now),
                    )
                )
            )
            .scalars()
            .all()
        )
        return {
            item_id: ShareBadges(
                shared_with_users=item_id in shared,
                has_active_public_link=item_id in linked,
            )
            for item_id in item_ids
        }


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

    async def get_by_id(self, link_id: UUID) -> ShareLink | None:
        result = await self._session.execute(select(ShareLink).where(ShareLink.id == link_id))
        return result.scalar_one_or_none()

    async def update_attempt_state(
        self,
        link_id: UUID,
        *,
        window_start: datetime | None,
        count: int,
        locked_until: datetime | None,
    ) -> None:
        await self._session.execute(
            update(ShareLink)
            .where(ShareLink.id == link_id)
            .values(
                attempt_window_start=window_start,
                attempt_count=count,
                locked_until=locked_until,
            )
        )
        await self._session.flush()

    async def deactivate(self, link_id: UUID) -> None:
        result = await self._session.execute(select(ShareLink).where(ShareLink.id == link_id))
        link = result.scalar_one()
        link.is_active = False
        await self._session.flush()
