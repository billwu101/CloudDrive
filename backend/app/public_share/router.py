"""Guest routes for public share links.

No route here may depend on ``CurrentUserId``: these are reached by people
without an account. Authorisation comes from the share access credential
(``ShareToken``) and is re-verified against the database on every request.
"""

from __future__ import annotations

import urllib.parse
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from app.core.dependencies import DbSession
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.download.service import DownloadService
from app.drive.repository import SQLDriveItemRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.preview.service import PreviewService
from app.public_share.schemas import (
    PublicItemResponse,
    PublicSessionRequest,
    PublicSessionResponse,
)
from app.public_share.service import PublicShareService
from app.schemas.common import Page
from app.share.repository import SQLShareLinkRepository
from app.storage.factory import get_storage_provider

router = APIRouter(prefix="/public", tags=["public-share"])


def _public_share_service(session: DbSession) -> PublicShareService:
    from app.core.config import get_settings

    settings = get_settings()
    storage = get_storage_provider(settings)
    items = SQLDriveItemRepository(session)
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


def _attachment_headers(filename: str, size: int | None) -> dict[str, str]:
    quoted = urllib.parse.quote(filename)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"}
    if size is not None:
        headers["Content-Length"] = str(size)
    return headers
