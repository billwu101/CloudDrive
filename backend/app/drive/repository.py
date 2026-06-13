from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID, uuid4

from sqlalchemy import asc, case, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.drive.schemas import DriveItemSortField
from app.models.drive_item import DriveItem
from app.models.user_item_preference import UserItemPreference
from app.schemas.common import SortOrder


class AbstractDriveItemRepository(ABC):
    @abstractmethod
    async def get_by_id(self, item_id: UUID) -> DriveItem | None: ...

    @abstractmethod
    async def list_children(
        self,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        sort_by: DriveItemSortField,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[DriveItem], int]: ...

    @abstractmethod
    async def create(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID | None,
        item_type: str,
        name: str,
        created_by: UUID,
    ) -> DriveItem: ...

    @abstractmethod
    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem: ...

    @abstractmethod
    async def update_parent(
        self, item_id: UUID, parent_id: UUID | None, updated_by: UUID
    ) -> DriveItem: ...

    @abstractmethod
    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool: ...


class SQLDriveItemRepository(AbstractDriveItemRepository):  # pragma: no cover
    _SORT_COLUMNS: ClassVar[dict[str, InstrumentedAttribute[Any]]] = {
        DriveItemSortField.NAME: DriveItem.name,
        DriveItemSortField.CREATED_AT: DriveItem.created_at,
        DriveItemSortField.UPDATED_AT: DriveItem.updated_at,
        DriveItemSortField.SIZE_BYTES: DriveItem.size_bytes,
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, item_id: UUID) -> DriveItem | None:
        result = await self._session.execute(select(DriveItem).where(DriveItem.id == item_id))
        return result.scalar_one_or_none()

    async def list_children(
        self,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        sort_by: DriveItemSortField,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[DriveItem], int]:
        base = select(DriveItem).where(
            DriveItem.owner_id == owner_id,
            DriveItem.is_deleted.is_(False),
            DriveItem.parent_id == parent_id
            if parent_id is not None
            else DriveItem.parent_id.is_(None),
        )
        sort_col = self._SORT_COLUMNS.get(sort_by, DriveItem.name)
        folder_first = case((DriveItem.item_type == "FOLDER", 0), else_=1)
        direction = asc if order == SortOrder.ASC else desc
        stmt = base.order_by(folder_first, direction(sort_col)).offset(offset).limit(limit)
        count_stmt = select(DriveItem.id).where(
            DriveItem.owner_id == owner_id,
            DriveItem.is_deleted.is_(False),
            DriveItem.parent_id == parent_id
            if parent_id is not None
            else DriveItem.parent_id.is_(None),
        )
        rows = await self._session.execute(stmt)
        count_result = await self._session.execute(count_stmt)
        items = list(rows.scalars().all())
        total = len(count_result.all())
        return items, total

    async def create(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID | None,
        item_type: str,
        name: str,
        created_by: UUID,
    ) -> DriveItem:
        now = datetime.now(UTC)
        item = DriveItem(
            id=uuid4(),
            owner_id=owner_id,
            parent_id=parent_id,
            item_type=item_type,
            name=name,
            mime_type=None,
            extension=None,
            size_bytes=0,
            storage_key=None,
            checksum_sha256=None,
            is_starred=False,
            is_deleted=False,
            deleted_at=None,
            created_by=created_by,
            updated_by=None,
            created_at=now,
            updated_at=now,
        )
        self._session.add(item)
        await self._session.flush()
        return item

    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem:
        now = datetime.now(UTC)
        item = await self.get_by_id(item_id)
        assert item is not None
        item.name = name
        item.updated_by = updated_by
        item.updated_at = now
        await self._session.flush()
        return item

    async def update_parent(
        self, item_id: UUID, parent_id: UUID | None, updated_by: UUID
    ) -> DriveItem:
        now = datetime.now(UTC)
        item = await self.get_by_id(item_id)
        assert item is not None
        item.parent_id = parent_id
        item.updated_by = updated_by
        item.updated_at = now
        await self._session.flush()
        return item

    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        stmt = select(DriveItem.id).where(
            DriveItem.owner_id == owner_id,
            DriveItem.is_deleted.is_(False),
            DriveItem.name == name,
            DriveItem.parent_id == parent_id
            if parent_id is not None
            else DriveItem.parent_id.is_(None),
        )
        if exclude_id is not None:
            stmt = stmt.where(DriveItem.id != exclude_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


class AbstractUserItemPreferenceRepository(ABC):
    @abstractmethod
    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None: ...

    @abstractmethod
    async def upsert_preference(
        self, user_id: UUID, item_id: UUID, *, is_starred: bool
    ) -> UserItemPreference: ...

    @abstractmethod
    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]: ...


class SQLUserItemPreferenceRepository(AbstractUserItemPreferenceRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None:
        result = await self._session.execute(
            select(UserItemPreference).where(
                UserItemPreference.user_id == user_id,
                UserItemPreference.item_id == item_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_preference(
        self, user_id: UUID, item_id: UUID, *, is_starred: bool
    ) -> UserItemPreference:
        now = datetime.now(UTC)
        pref = await self.get_preference(user_id, item_id)
        if pref is None:
            pref = UserItemPreference(
                id=uuid4(),
                user_id=user_id,
                item_id=item_id,
                is_starred=is_starred,
                created_at=now,
                updated_at=now,
            )
            self._session.add(pref)
        else:
            pref.is_starred = is_starred
            pref.updated_at = now
        await self._session.flush()
        return pref

    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]:
        if not item_ids:
            return set()
        result = await self._session.execute(
            select(UserItemPreference.item_id).where(
                UserItemPreference.user_id == user_id,
                UserItemPreference.item_id.in_(item_ids),
                UserItemPreference.is_starred.is_(True),
            )
        )
        return {row[0] for row in result.all()}
