from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, UploadFile

from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository
from app.file_version.repository import SQLFileVersionRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.schemas.common import DriveItemResponse
from app.search.factory import build_search_index_service
from app.storage.factory import get_storage_provider
from app.upload.service import UploadService
from app.users.repository import SQLUserRepository
from app.users.service import QuotaService

router = APIRouter(prefix="/upload", tags=["upload"])


def _upload_service(session: DbSession) -> UploadService:
    from app.core.config import get_settings

    settings = get_settings()
    return UploadService(
        item_repo=SQLDriveItemRepository(session),
        version_repo=SQLFileVersionRepository(session),
        storage=get_storage_provider(settings),
        permission_svc=PermissionService(
            share_repo=SQLShareRepository(session),
            item_repo=SQLDriveItemRepository(session),
        ),
        quota_svc=QuotaService(repo=SQLUserRepository(session)),
        search_indexer=build_search_index_service(session, settings),
    )


UploadServiceDep = Annotated[UploadService, Depends(_upload_service)]


@router.post(
    "/simple",
    response_model=DriveItemResponse,
    status_code=201,
    summary="Upload a file (simple multipart)",
)
async def upload_simple(
    file: UploadFile,
    current_user_id: CurrentUserId,
    service: UploadServiceDep,
    session: DbSession,
    parent_id: str | None = None,
) -> DriveItemResponse:
    from uuid import UUID

    pid = UUID(parent_id) if parent_id else None

    async def _stream() -> AsyncGenerator[bytes, None]:
        while chunk := await file.read(65536):
            yield chunk

    result = await service.upload_simple(
        user_id=current_user_id,
        parent_id=pid,
        filename=file.filename or "unnamed",
        stream=_stream(),
        size_bytes=file.size or 0,
        mime_type=file.content_type,
    )
    await session.commit()
    return result
