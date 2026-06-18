from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository
from app.file_version.repository import SQLFileVersionRepository
from app.permission.repository import SQLShareRepository
from app.schemas.common import DriveItemResponse, Page
from app.snapshot.repository import SQLSnapshotRepository
from app.storage.factory import get_storage_provider
from app.trash.repository import SQLTrashRepository
from app.trash.service import TrashService
from app.users.repository import SQLUserRepository
from app.users.service import QuotaService

router = APIRouter(prefix="/trash", tags=["trash"])


def _trash_service(session: DbSession) -> TrashService:
    from app.core.config import get_settings

    settings = get_settings()
    return TrashService(
        item_repo=SQLDriveItemRepository(session),
        trash_repo=SQLTrashRepository(session),
        version_repo=SQLFileVersionRepository(session),
        share_repo=SQLShareRepository(session),
        storage=get_storage_provider(settings),
        quota_svc=QuotaService(repo=SQLUserRepository(session)),
        snapshot_refs=SQLSnapshotRepository(session),
    )


TrashServiceDep = Annotated[TrashService, Depends(_trash_service)]


@router.post(
    "/items/{item_id}",
    response_model=DriveItemResponse,
    summary="Move item to trash",
)
async def move_to_trash(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: TrashServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.trash_item(current_user_id, item_id)
    await session.commit()
    return result


@router.get("", response_model=Page[DriveItemResponse], summary="List trash")
async def list_trash(
    current_user_id: CurrentUserId,
    service: TrashServiceDep,
    page: int = 1,
    page_size: int = 50,
) -> Page[DriveItemResponse]:
    return await service.list_trash(current_user_id, page=page, page_size=page_size)


@router.post(
    "/items/{item_id}/restore",
    response_model=DriveItemResponse,
    summary="Restore item from trash",
)
async def restore_item(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: TrashServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.restore(current_user_id, item_id)
    await session.commit()
    return result


@router.delete(
    "/items/{item_id}",
    status_code=204,
    summary="Permanently delete item",
)
async def permanent_delete(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: TrashServiceDep,
    session: DbSession,
) -> None:
    await service.permanent_delete(current_user_id, item_id)
    await session.commit()


@router.delete(
    "",
    status_code=204,
    summary="Empty trash (permanently delete all trashed items)",
)
async def empty_trash(
    current_user_id: CurrentUserId,
    service: TrashServiceDep,
    session: DbSession,
) -> None:
    await service.empty_trash(current_user_id)
    await session.commit()
