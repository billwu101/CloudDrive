from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, UploadFile

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository
from app.file_version.repository import SQLFileVersionRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.schemas.common import DriveItemResponse
from app.search.factory import build_search_index_service
from app.storage.factory import get_storage_provider
from app.upload.schemas import CreateUploadSessionRequest, UploadSessionResponse
from app.upload.service import UploadService
from app.upload.session_repository import SQLUploadSessionRepository
from app.upload.session_service import UploadSessionService, UploadSessionStatus
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


def _upload_session_service(session: DbSession) -> UploadSessionService:
    from app.core.config import get_settings

    settings = get_settings()
    return UploadSessionService(
        session_repo=SQLUploadSessionRepository(session),
        item_repo=SQLDriveItemRepository(session),
        version_repo=SQLFileVersionRepository(session),
        storage=get_storage_provider(settings),
        permission_svc=PermissionService(
            share_repo=SQLShareRepository(session),
            item_repo=SQLDriveItemRepository(session),
        ),
        quota_svc=QuotaService(repo=SQLUserRepository(session)),
        activity_svc=ActivityLogService(repo=SQLActivityLogRepository(session)),
        chunk_size=settings.upload_chunk_size_bytes,
        max_file_size=settings.max_chunked_upload_size_bytes,
        retention_days=settings.upload_session_retention_days,
    )


UploadSessionServiceDep = Annotated[UploadSessionService, Depends(_upload_session_service)]


def _to_session_response(status: UploadSessionStatus) -> UploadSessionResponse:
    session = status.session
    return UploadSessionResponse(
        id=session.id,
        filename=session.filename,
        total_size=session.total_size,
        chunk_size=session.chunk_size,
        total_chunks=session.total_chunks,
        status=session.status,
        uploaded_chunks=status.uploaded_chunks,
        expires_at=session.expires_at,
    )


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


@router.post(
    "/sessions",
    response_model=UploadSessionResponse,
    status_code=201,
    summary="Start a chunked resumable upload",
)
async def create_upload_session(
    payload: CreateUploadSessionRequest,
    current_user_id: CurrentUserId,
    service: UploadSessionServiceDep,
    session: DbSession,
) -> UploadSessionResponse:
    status = await service.create_session(
        current_user_id,
        filename=payload.filename,
        total_size=payload.total_size,
        parent_id=payload.parent_id,
        mime_type=payload.mime_type,
    )
    await session.commit()
    return _to_session_response(status)


@router.get(
    "/sessions/{session_id}",
    response_model=UploadSessionResponse,
    summary="Get session status and the chunk indexes already stored",
)
async def get_upload_session(
    session_id: UUID,
    current_user_id: CurrentUserId,
    service: UploadSessionServiceDep,
) -> UploadSessionResponse:
    return _to_session_response(await service.get_session(current_user_id, session_id))


@router.put(
    "/sessions/{session_id}/chunks/{chunk_index}",
    status_code=204,
    summary="Upload one chunk (idempotent: re-sending an index overwrites it)",
)
async def upload_chunk(
    session_id: UUID,
    chunk_index: int,
    request: Request,
    current_user_id: CurrentUserId,
    service: UploadSessionServiceDep,
    session: DbSession,
) -> Response:
    # Read straight off the request body so a chunk never lands in memory
    # whole; the body is the raw bytes, not multipart.
    await service.upload_chunk(current_user_id, session_id, chunk_index, request.stream())
    await session.commit()
    return Response(status_code=204)


@router.post(
    "/sessions/{session_id}/complete",
    response_model=DriveItemResponse,
    status_code=201,
    summary="Merge the chunks into the final file",
)
async def complete_upload_session(
    session_id: UUID,
    current_user_id: CurrentUserId,
    service: UploadSessionServiceDep,
    session: DbSession,
) -> DriveItemResponse:
    result = await service.complete_session(current_user_id, session_id)
    await session.commit()
    return result


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Cancel a session and delete its stored chunks",
)
async def cancel_upload_session(
    session_id: UUID,
    current_user_id: CurrentUserId,
    service: UploadSessionServiceDep,
    session: DbSession,
) -> Response:
    await service.cancel_session(current_user_id, session_id)
    await session.commit()
    return Response(status_code=204)
