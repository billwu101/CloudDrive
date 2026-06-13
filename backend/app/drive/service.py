from __future__ import annotations

from uuid import UUID

from app.activity_log.actions import ActivityAction
from app.activity_log.service import ActivityLogService
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.drive.repository import (
    AbstractDriveItemRepository,
    AbstractUserItemPreferenceRepository,
)
from app.drive.schemas import DriveItemSortField, ItemType
from app.models.drive_item import DriveItem
from app.schemas.common import DriveItemResponse, Page, SortOrder

_INVALID_NAME_CHARS = frozenset("/\\\x00")
_MAX_NAME_LEN = 512


def _validate_name(name: str) -> str:
    name = name.strip()
    if not name:
        raise AppError(ErrorCode.INVALID_OPERATION, "Name cannot be empty")
    if len(name) > _MAX_NAME_LEN:
        raise AppError(ErrorCode.INVALID_OPERATION, f"Name too long (max {_MAX_NAME_LEN})")
    if any(c in name for c in _INVALID_NAME_CHARS):
        raise AppError(ErrorCode.INVALID_OPERATION, "Name contains invalid characters (/ \\ \\0)")
    return name


def _to_response(item: DriveItem, *, is_starred: bool) -> DriveItemResponse:
    return DriveItemResponse(
        id=item.id,
        owner_id=item.owner_id,
        parent_id=item.parent_id,
        item_type=item.item_type,
        name=item.name,
        mime_type=item.mime_type,
        extension=item.extension,
        size_bytes=item.size_bytes,
        is_starred=is_starred,
        is_deleted=item.is_deleted,
        deleted_at=item.deleted_at,
        created_by=item.created_by,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


class DriveService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        pref_repo: AbstractUserItemPreferenceRepository,
        activity_svc: ActivityLogService | None = None,
    ) -> None:
        self._items = item_repo
        self._prefs = pref_repo
        self._activity = activity_svc

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _get_owned(self, item_id: UUID, user_id: UUID) -> DriveItem:
        item = await self._items.get_by_id(item_id)
        if item is None or item.is_deleted:
            raise NotFoundError("Item not found")
        if item.owner_id != user_id:
            raise ForbiddenError()
        return item

    async def _is_descendant_or_self(self, candidate_id: UUID, target_id: UUID) -> bool:
        """Return True if target_id equals or is a descendant of candidate_id."""
        current_id: UUID | None = target_id
        seen: set[UUID] = set()
        while current_id is not None:
            if current_id == candidate_id:
                return True
            if current_id in seen:
                break
            seen.add(current_id)
            item = await self._items.get_by_id(current_id)
            if item is None:
                break
            current_id = item.parent_id
        return False

    async def _starred(self, user_id: UUID, items: list[DriveItem]) -> set[UUID]:
        return await self._prefs.get_starred_ids(user_id, [i.id for i in items])

    async def _log(
        self,
        *,
        actor_id: UUID,
        action: str,
        item_id: UUID | None = None,
    ) -> None:
        if self._activity is not None:
            await self._activity.log(actor_id=actor_id, action=action, item_id=item_id)

    # ── Public API ──────────────────────────────────────────────────────────

    async def get_raw_item(self, user_id: UUID, item_id: UUID) -> DriveItem:
        """Return the raw DriveItem model (ownership-checked). Used by downstream services."""
        return await self._get_owned(item_id, user_id)

    async def get_item(self, user_id: UUID, item_id: UUID) -> DriveItemResponse:
        item = await self._get_owned(item_id, user_id)
        starred = await self._starred(user_id, [item])
        return _to_response(item, is_starred=item.id in starred)

    async def list_items(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        *,
        page: int = 1,
        page_size: int = 20,
        sort_by: DriveItemSortField = DriveItemSortField.NAME,
        order: SortOrder = SortOrder.ASC,
    ) -> Page[DriveItemResponse]:
        if parent_id is not None:
            parent = await self._items.get_by_id(parent_id)
            if parent is None or parent.is_deleted:
                raise NotFoundError("Folder not found")
            if parent.owner_id != user_id:
                raise ForbiddenError()
        offset = (page - 1) * page_size
        items, total = await self._items.list_children(
            parent_id,
            user_id,
            sort_by=sort_by,
            order=order,
            offset=offset,
            limit=page_size,
        )
        starred = await self._starred(user_id, items)
        responses = [_to_response(i, is_starred=i.id in starred) for i in items]
        return Page[DriveItemResponse].create(responses, total, page=page, page_size=page_size)

    async def create_folder(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        name: str,
    ) -> DriveItemResponse:
        name = _validate_name(name)
        if parent_id is not None:
            parent = await self._items.get_by_id(parent_id)
            if parent is None or parent.is_deleted:
                raise NotFoundError("Parent folder not found")
            if parent.owner_id != user_id:
                raise ForbiddenError()
            if parent.item_type != ItemType.FOLDER:
                raise AppError(ErrorCode.INVALID_OPERATION, "Parent must be a folder")
        if await self._items.name_exists_in_parent(name, parent_id, user_id):
            raise AppError(ErrorCode.NAME_CONFLICT, f"'{name}' already exists in this location")
        item = await self._items.create(
            owner_id=user_id,
            parent_id=parent_id,
            item_type=ItemType.FOLDER,
            name=name,
            created_by=user_id,
        )
        await self._log(actor_id=user_id, action=ActivityAction.CREATE, item_id=item.id)
        return _to_response(item, is_starred=False)

    async def rename(
        self,
        user_id: UUID,
        item_id: UUID,
        new_name: str,
    ) -> DriveItemResponse:
        new_name = _validate_name(new_name)
        item = await self._get_owned(item_id, user_id)
        if item.name == new_name:
            return _to_response(item, is_starred=item.id in await self._starred(user_id, [item]))
        if await self._items.name_exists_in_parent(
            new_name, item.parent_id, user_id, exclude_id=item_id
        ):
            raise AppError(ErrorCode.NAME_CONFLICT, f"'{new_name}' already exists in this location")
        updated = await self._items.update_name(item_id, new_name, user_id)
        await self._log(actor_id=user_id, action=ActivityAction.RENAME, item_id=item_id)
        starred = await self._starred(user_id, [updated])
        return _to_response(updated, is_starred=item_id in starred)

    async def move(
        self,
        user_id: UUID,
        item_id: UUID,
        new_parent_id: UUID | None,
    ) -> DriveItemResponse:
        item = await self._get_owned(item_id, user_id)
        if new_parent_id is not None:
            new_parent = await self._items.get_by_id(new_parent_id)
            if new_parent is None or new_parent.is_deleted:
                raise NotFoundError("Destination folder not found")
            if new_parent.owner_id != user_id:
                raise ForbiddenError()
            if new_parent.item_type != ItemType.FOLDER:
                raise AppError(ErrorCode.INVALID_OPERATION, "Destination must be a folder")
            if item.item_type == ItemType.FOLDER and await self._is_descendant_or_self(
                item_id, new_parent_id
            ):
                raise AppError(
                    ErrorCode.INVALID_OPERATION,
                    "Cannot move a folder into itself or its descendants",
                )
        if await self._items.name_exists_in_parent(
            item.name, new_parent_id, user_id, exclude_id=item_id
        ):
            raise AppError(ErrorCode.NAME_CONFLICT, f"'{item.name}' already exists in destination")
        updated = await self._items.update_parent(item_id, new_parent_id, user_id)
        await self._log(actor_id=user_id, action=ActivityAction.MOVE, item_id=item_id)
        starred = await self._starred(user_id, [updated])
        return _to_response(updated, is_starred=item_id in starred)

    async def set_starred(
        self,
        user_id: UUID,
        item_id: UUID,
        is_starred: bool,
    ) -> DriveItemResponse:
        item = await self._get_owned(item_id, user_id)
        await self._prefs.upsert_preference(user_id, item_id, is_starred=is_starred)
        await self._log(actor_id=user_id, action=ActivityAction.STAR, item_id=item_id)
        return _to_response(item, is_starred=is_starred)

    async def get_ancestors(self, user_id: UUID, item_id: UUID) -> list[DriveItemResponse]:
        """Return [root_folder, ..., direct_parent] for item_id. Current item excluded."""
        item = await self._get_owned(item_id, user_id)
        chain: list[DriveItem] = []
        current_parent_id = item.parent_id
        seen: set[UUID] = set()
        while current_parent_id is not None:
            if current_parent_id in seen:
                break
            seen.add(current_parent_id)
            parent = await self._items.get_by_id(current_parent_id)
            if parent is None:
                break
            chain.append(parent)
            current_parent_id = parent.parent_id
        chain.reverse()
        starred = await self._starred(user_id, chain) if chain else set()
        return [_to_response(a, is_starred=a.id in starred) for a in chain]

    async def get_recent(
        self,
        user_id: UUID,
        *,
        limit: int = 20,
    ) -> list[DriveItemResponse]:
        if self._activity is None:
            return []
        item_ids = await self._activity.get_recent_item_ids(user_id, limit=limit)
        responses: list[DriveItemResponse] = []
        item_list: list[DriveItem] = []
        for iid in item_ids:
            item = await self._items.get_by_id(iid)
            if item is not None and not item.is_deleted and item.owner_id == user_id:
                item_list.append(item)
        if not item_list:
            return []
        starred = await self._starred(user_id, item_list)
        for item in item_list:
            responses.append(_to_response(item, is_starred=item.id in starred))
        return responses
