"""Guest routes for public share links.

No route here may depend on ``CurrentUserId``: these are reached by people
without an account. Authorisation comes from the share access credential
(``ShareToken``) and is re-verified against the database on every request.
"""

from __future__ import annotations

import urllib.parse
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.activity_log.actions import ActivityAction
from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.core.dependencies import DbSession
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.download.service import DownloadService
from app.drive.repository import SQLDriveItemRepository, SQLUserItemPreferenceRepository
from app.drive.service import DriveService
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.preview.service import PreviewService
from app.public_share.schemas import (
    PublicItemResponse,
    PublicSessionRequest,
    PublicSessionResponse,
)
from app.public_share.service import PublicShareService
from app.public_share.service import _to_public_item as _to_public
from app.schemas.common import Page
from app.share.repository import SQLShareLinkRepository
from app.storage.factory import get_storage_provider
from app.trash.router import _trash_service
from app.upload.router import _upload_service

router = APIRouter(prefix="/public", tags=["public-share"])


def _public_share_service(session: DbSession) -> PublicShareService:
    from app.core.config import get_settings

    settings = get_settings()
    storage = get_storage_provider(settings)
    items = SQLDriveItemRepository(session)
    activity_svc = ActivityLogService(SQLActivityLogRepository(session))
    permission_svc = PermissionService(
        share_repo=SQLShareRepository(session),
        item_repo=SQLDriveItemRepository(session),
    )
    return PublicShareService(
        item_repo=items,
        link_repo=SQLShareLinkRepository(session),
        storage=storage,
        preview_svc=PreviewService(item_repo=items, storage=storage, permission_svc=permission_svc),
        download_svc=DownloadService(
            item_repo=items, storage=storage, permission_svc=permission_svc
        ),
        # Write paths (proposal §33). These run as the item's owner — the guard
        # that keeps a guest to editor's abilities lives in PublicShareService,
        # not here.
        drive_svc=DriveService(
            item_repo=items,
            pref_repo=SQLUserItemPreferenceRepository(session),
            activity_svc=activity_svc,
            permission_svc=permission_svc,
        ),
        upload_svc=_upload_service(session),
        trash_svc=_trash_service(session),
    )


ServiceDep = Annotated[PublicShareService, Depends(_public_share_service)]


def share_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Pull the share credential out of the Authorization header.

    Intentionally not reusing the user-auth dependency: that one resolves a
    user id, which no guest has.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise AppError(ErrorCode.SHARE_LINK_INVALID, "Missing share credential", status_code=401)
    return authorization[7:].strip()


ShareToken = Annotated[str, Depends(share_token)]


@router.post(
    "/links/{token}/session",
    response_model=PublicSessionResponse,
    summary="Open a guest session for a share link",
)
async def open_session(
    token: str,
    body: PublicSessionRequest,
    service: ServiceDep,
    session: DbSession,
) -> PublicSessionResponse:
    try:
        result = await service.open_session(token, body.password)
    finally:
        # Attempt counters must survive even when the attempt failed —
        # otherwise the rate limit could be reset by simply failing.
        await session.commit()
    return result


@router.post(
    "/links/{token}/session/refresh",
    response_model=PublicSessionResponse,
    summary="Extend a guest session",
)
async def refresh_session(
    token: str,
    credential: ShareToken,
    service: ServiceDep,
) -> PublicSessionResponse:
    return await service.refresh_session(credential)


@router.get("/items", response_model=PublicItemResponse, summary="Shared item metadata")
async def get_root(credential: ShareToken, service: ServiceDep) -> PublicItemResponse:
    return await service.get_root(credential)


@router.get(
    "/items/{item_id}/children",
    response_model=Page[PublicItemResponse],
    summary="Browse a shared folder",
)
async def list_children(
    item_id: UUID,
    credential: ShareToken,
    service: ServiceDep,
    page: int = 1,
    page_size: int = 50,
) -> Page[PublicItemResponse]:
    return await service.list_children(credential, item_id, page=page, page_size=page_size)


@router.get("/items/{item_id}/preview", summary="Preview a shared file")
async def preview(
    item_id: UUID,
    credential: ShareToken,
    service: ServiceDep,
) -> StreamingResponse:
    mime, stream = await service.preview(credential, item_id)
    return StreamingResponse(stream, media_type=mime)


@router.get("/items/{item_id}/download", summary="Download a shared file")
async def download(
    item_id: UUID,
    credential: ShareToken,
    service: ServiceDep,
) -> StreamingResponse:
    result = await service.download(credential, item_id)
    return StreamingResponse(
        result.stream,
        media_type=result.mime_type,
        headers=_attachment_headers(result.filename, result.size_bytes),
    )


@router.get("/archive", summary="Download the shared folder as a zip")
async def archive(credential: ShareToken, service: ServiceDep) -> StreamingResponse:
    result = await service.archive(credential)
    return StreamingResponse(
        result.stream,
        media_type="application/zip",
        headers=_attachment_headers(result.filename, None),
    )


class CreateFolderBody(BaseModel):
    parent_id: UUID
    name: str


class RenameBody(BaseModel):
    name: str


class MoveBody(BaseModel):
    parent_id: UUID


async def _audit_guest_write(
    service: PublicShareService,
    session: DbSession,
    credential: str,
    request: Request,
    *,
    action: str,
    item_id: UUID,
) -> None:
    """Record a guest write truthfully.

    `actor_id` is the link's creator because the data lands in their drive and
    counts against their quota — that part is fact. What stops the row from
    reading as "the owner did this" is `via_share_link_id`, plus the visitor's
    address (design §6.12.11b).
    """
    who = await service.audit_context(credential)
    await ActivityLogService(SQLActivityLogRepository(session)).log(
        actor_id=who.owner_id,
        action=action,
        item_id=item_id,
        metadata={"via_share_link_id": str(who.link_id)},
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.post("/folders", response_model=PublicItemResponse, summary="Create a folder")
async def create_folder(
    body: CreateFolderBody,
    credential: ShareToken,
    service: ServiceDep,
    session: DbSession,
    request: Request,
) -> PublicItemResponse:
    item = await service.create_folder(credential, body.parent_id, body.name)
    await _audit_guest_write(
        service, session, credential, request, action=ActivityAction.CREATE, item_id=item.id
    )
    await session.commit()
    return _to_public(item)


@router.post(
    "/items/{item_id}/upload", response_model=PublicItemResponse, summary="Upload into a folder"
)
async def upload(
    item_id: UUID,
    credential: ShareToken,
    service: ServiceDep,
    session: DbSession,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> PublicItemResponse:
    created = await service.upload(
        credential,
        item_id,
        filename=file.filename or "upload",
        stream=_stream(file),
        size_bytes=file.size or 0,
        mime_type=file.content_type,
    )
    await _audit_guest_write(
        service, session, credential, request, action=ActivityAction.UPLOAD, item_id=created.id
    )
    await session.commit()
    return _to_public(created)


@router.patch("/items/{item_id}/name", response_model=PublicItemResponse, summary="Rename")
async def rename(
    item_id: UUID,
    body: RenameBody,
    credential: ShareToken,
    service: ServiceDep,
    session: DbSession,
    request: Request,
) -> PublicItemResponse:
    item = await service.rename(credential, item_id, body.name)
    await _audit_guest_write(
        service, session, credential, request, action=ActivityAction.RENAME, item_id=item.id
    )
    await session.commit()
    return _to_public(item)


@router.patch("/items/{item_id}/parent", response_model=PublicItemResponse, summary="Move")
async def move(
    item_id: UUID,
    body: MoveBody,
    credential: ShareToken,
    service: ServiceDep,
    session: DbSession,
    request: Request,
) -> PublicItemResponse:
    item = await service.move(credential, item_id, body.parent_id)
    await _audit_guest_write(
        service, session, credential, request, action=ActivityAction.MOVE, item_id=item.id
    )
    await session.commit()
    return _to_public(item)


@router.post("/items/{item_id}/trash", status_code=204, summary="Move to trash")
async def trash(
    item_id: UUID,
    credential: ShareToken,
    service: ServiceDep,
    session: DbSession,
    request: Request,
) -> None:
    await service.trash(credential, item_id)
    await _audit_guest_write(
        service, session, credential, request, action=ActivityAction.TRASH, item_id=item_id
    )
    await session.commit()


async def _stream(file: UploadFile) -> AsyncGenerator[bytes, None]:
    while chunk := await file.read(1024 * 1024):
        yield chunk


def _attachment_headers(filename: str, size: int | None) -> dict[str, str]:
    quoted = urllib.parse.quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}
    if size is not None:
        headers["Content-Length"] = str(size)
    return headers
