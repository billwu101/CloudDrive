from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.preview.service import PreviewInfoResponse, PreviewService
from app.storage.factory import get_storage_provider

router = APIRouter(prefix="/preview", tags=["preview"])


def _preview_service(session: DbSession) -> PreviewService:
    from app.core.config import get_settings

    settings = get_settings()
    return PreviewService(
        item_repo=SQLDriveItemRepository(session),
        storage=get_storage_provider(settings),
        permission_svc=PermissionService(
            share_repo=SQLShareRepository(session),
            item_repo=SQLDriveItemRepository(session),
        ),
    )


PreviewServiceDep = Annotated[PreviewService, Depends(_preview_service)]


@router.get("/{item_id}", response_model=PreviewInfoResponse, summary="Get preview info")
async def get_preview_info(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: PreviewServiceDep,
) -> PreviewInfoResponse:
    return await service.get_info(current_user_id, item_id)


@router.get("/{item_id}/content", summary="Stream preview content")
async def get_preview_content(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: PreviewServiceDep,
) -> StreamingResponse:
    _, mime, stream = await service.get_content(current_user_id, item_id)
    return StreamingResponse(stream, media_type=mime)
