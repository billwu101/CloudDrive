from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository, SQLUserItemPreferenceRepository
from app.drive.schemas import (
    CreateFolderRequest,
    DriveItemSortField,
    MoveRequest,
    RenameRequest,
    StarRequest,
)
from app.drive.service import DriveService
from app.schemas.common import DriveItemResponse, Page, SortOrder

router = APIRouter(prefix="/drive", tags=["drive"])


def _drive_service(session: DbSession) -> DriveService:
    return DriveService(
        item_repo=SQLDriveItemRepository(session),
        pref_repo=SQLUserItemPreferenceRepository(session),
        activity_svc=ActivityLogService(SQLActivityLogRepository(session)),
    )


DriveServiceDep = Annotated[DriveService, Depends(_drive_service)]


@router.get(
    "/items",
    response_model=Page[DriveItemResponse],
    summary="List drive items (root or folder contents)",
)
async def list_items(
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    parent_id: UUID | None = Query(default=None),  # noqa: B008
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    sort_by: DriveItemSortField = Query(default=DriveItemSortField.NAME),  # noqa: B008
    order: SortOrder = Query(default=SortOrder.ASC),  # noqa: B008
) -> Page[DriveItemResponse]:
    return await service.list_items(
        current_user_id,
        parent_id,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        order=order,
    )


@router.get(
    "/items/{item_id}",
    response_model=DriveItemResponse,
    summary="Get a single drive item",
)
async def get_item(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
) -> DriveItemResponse:
    return await service.get_item(current_user_id, item_id)


@router.post(
    "/folders",
    response_model=DriveItemResponse,
    status_code=201,
    summary="Create a new folder",
    responses={409: {"description": "Name conflict"}, 404: {"description": "Parent not found"}},
)
async def create_folder(
    body: CreateFolderRequest,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.create_folder(current_user_id, body.parent_id, body.name)
    await session.commit()
    return result


@router.patch(
    "/items/{item_id}/name",
    response_model=DriveItemResponse,
    summary="Rename a drive item",
)
async def rename_item(
    item_id: UUID,
    body: RenameRequest,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.rename(current_user_id, item_id, body.name)
    await session.commit()
    return result


@router.patch(
    "/items/{item_id}/parent",
    response_model=DriveItemResponse,
    summary="Move a drive item to a different folder",
)
async def move_item(
    item_id: UUID,
    body: MoveRequest,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.move(current_user_id, item_id, body.parent_id)
    await session.commit()
    return result


@router.put(
    "/items/{item_id}/star",
    response_model=DriveItemResponse,
    summary="Star or unstar a drive item",
)
async def star_item(
    item_id: UUID,
    body: StarRequest,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.set_starred(current_user_id, item_id, body.is_starred)
    await session.commit()
    return result


@router.get(
    "/items/{item_id}/ancestors",
    response_model=list[DriveItemResponse],
    summary="Get ancestor folders for a drive item (ordered root → direct parent)",
)
async def get_ancestors(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
) -> list[DriveItemResponse]:
    return await service.get_ancestors(current_user_id, item_id)


@router.get(
    "/recent",
    response_model=list[DriveItemResponse],
    summary="Get recently accessed drive items",
)
async def get_recent(
    current_user_id: CurrentUserId,
    service: DriveServiceDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[DriveItemResponse]:
    return await service.get_recent(current_user_id, limit=limit)
