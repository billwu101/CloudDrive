from __future__ import annotations

import urllib.parse
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.dependencies import CurrentUserId, DbSession
from app.download.service import DownloadService
from app.drive.repository import SQLDriveItemRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.storage.factory import get_storage_provider

router = APIRouter(prefix="/download", tags=["download"])


class ArchiveRequest(BaseModel):
    item_ids: list[UUID]


def _download_service(session: DbSession) -> DownloadService:
    from app.core.config import get_settings

    settings = get_settings()
    return DownloadService(
        item_repo=SQLDriveItemRepository(session),
        storage=get_storage_provider(settings),
        permission_svc=PermissionService(
            share_repo=SQLShareRepository(session),
            item_repo=SQLDriveItemRepository(session),
        ),
    )


DownloadServiceDep = Annotated[DownloadService, Depends(_download_service)]


def _attachment_disposition(filename: str) -> str:
    encoded = urllib.parse.quote(filename, safe="")
    return f"attachment; filename*=UTF-8''{encoded}"


# Declared before "/{item_id}" so the literal path is not captured as an id.
@router.post("/archive", summary="Download multiple items as a zip")
async def download_archive(
    body: ArchiveRequest,
    current_user_id: CurrentUserId,
    service: DownloadServiceDep,
) -> StreamingResponse:
    result = await service.archive(current_user_id, body.item_ids)
    return StreamingResponse(
        result.stream,
        media_type="application/zip",
        headers={"Content-Disposition": _attachment_disposition(result.filename)},
    )


@router.get("/{item_id}", summary="Download a file")
async def download_file(
    item_id: UUID,
    current_user_id: CurrentUserId,
    service: DownloadServiceDep,
) -> StreamingResponse:
    result = await service.download(current_user_id, item_id)
    return StreamingResponse(
        result.stream,
        media_type=result.mime_type,
        headers={
            "Content-Disposition": _attachment_disposition(result.filename),
            "Content-Length": str(result.size_bytes),
        },
    )
