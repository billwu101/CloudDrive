from __future__ import annotations

from uuid import UUID

from app.core.exceptions import ForbiddenError
from app.drive.repository import AbstractDriveItemRepository
from app.models.drive_item import DriveItem
from app.permission.permissions import _LEVELS, Permission, has_at_least
from app.permission.repository import AbstractShareRepository


class PermissionService:
    def __init__(
        self,
        share_repo: AbstractShareRepository,
        item_repo: AbstractDriveItemRepository,
    ) -> None:
        self._shares = share_repo
        self._items = item_repo

    async def get_permission(self, user_id: UUID, item: DriveItem) -> Permission | None:
        """
        Walk the item → parent chain. First ownership check wins with OWNER.
        Otherwise collect the most permissive share found along the chain.
        """
        best: Permission | None = None
        current: DriveItem | None = item

        while current is not None:
            if current.owner_id == user_id:
                return Permission.OWNER

            share = await self._shares.get_by_item_and_user(current.id, user_id)
            if share is not None:
                candidate = Permission(share.permission)
                if best is None or _LEVELS[candidate] > _LEVELS[best]:
                    best = candidate

            if current.parent_id is None:
                break
            current = await self._items.get_by_id(current.parent_id)

        return best

    async def assert_can_view(self, user_id: UUID, item: DriveItem) -> None:
        perm = await self.get_permission(user_id, item)
        if not has_at_least(perm, Permission.VIEWER):
            raise ForbiddenError()

    async def assert_can_download(self, user_id: UUID, item: DriveItem) -> None:
        perm = await self.get_permission(user_id, item)
        if not has_at_least(perm, Permission.DOWNLOADER):
            raise ForbiddenError()

    async def assert_can_edit(self, user_id: UUID, item: DriveItem) -> None:
        perm = await self.get_permission(user_id, item)
        if not has_at_least(perm, Permission.EDITOR):
            raise ForbiddenError()

    async def assert_is_owner(self, user_id: UUID, item: DriveItem) -> None:
        perm = await self.get_permission(user_id, item)
        if perm is not Permission.OWNER:
            raise ForbiddenError()
