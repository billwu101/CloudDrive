from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository
from app.schemas.common import Page
from app.share.repository import SQLShareLinkRepository, SQLShareManagementRepository
from app.share.schemas import (
    SharedByMeEntry,
    ShareLinkRequest,
    ShareLinkResponse,
    ShareRequest,
    ShareResponse,
)
from app.share.service import ShareLinkService, ShareService
from app.users.repository import SQLUserRepository
from app.users.service import UserService

router = APIRouter(prefix="/share", tags=["share"])


def _share_service(session: DbSession) -> ShareService:
    return ShareService(
        item_repo=SQLDriveItemRepository(session),
        share_repo=SQLShareManagementRepository(session),
        user_svc=UserService(repo=SQLUserRepository(session)),
    )


def _link_service(session: DbSession) -> ShareLinkService:
    return ShareLinkService(
        item_repo=SQLDriveItemRepository(session),
        link_repo=SQLShareLinkRepository(session),
    )


ShareServiceDep = Annotated[ShareService, Depends(_share_service)]
LinkServiceDep = Annotated[ShareLinkService, Depends(_link_service)]


@router.post(
    "/items/{item_id}",
    response_model=ShareResponse,
    status_code=201,
    summary="Share item with a user",
)
async def share_item(
    item_id: UUID,
    body: ShareRequest,
    current_user_id: CurrentUserId,
    service: ShareServiceDep,
    session: DbSession,
) -> ShareResponse:
    result = await service.share_item(current_user_id, item_id, body.target_email, body.permission)
    await session.commit()
    return result


@router.delete(
    "/items/{item_id}/users/{target_user_id}",
    status_code=204,
    summary="Remove share",
)
async def remove_share(
    item_id: UUID,
    target_user_id: UUID,
    current_user_id: CurrentUserId,
    service: ShareServiceDep,
    session: DbSession,
) -> None:
    await service.remove_share(current_user_id, item_id, target_user_id)
    await session.commit()


@router.get(
    "/shared-with-me",
    response_model=Page[ShareResponse],
    summary="List items shared with me",
)
async def shared_with_me(
    current_user_id: CurrentUserId,
    service: ShareServiceDep,
    page: int = 1,
    page_size: int = 20,
) -> Page[ShareResponse]:
    return await service.list_shared_with_me(current_user_id, page=page, page_size=page_size)


@router.get(
    "/shared-by-me",
    response_model=Page[SharedByMeEntry],
    summary="List items I have shared out",
)
async def shared_by_me(
    current_user_id: CurrentUserId,
    service: ShareServiceDep,
    page: int = 1,
    page_size: int = 20,
) -> Page[SharedByMeEntry]:
    return await service.list_shared_by_me(current_user_id, page=page, page_size=page_size)


@router.post(
    "/items/{item_id}/links",
    response_model=ShareLinkResponse,
    status_code=201,
    summary="Create a public share link",
)
async def create_link(
    item_id: UUID,
    body: ShareLinkRequest,
    current_user_id: CurrentUserId,
    service: LinkServiceDep,
    session: DbSession,
) -> ShareLinkResponse:
    result = await service.create_link(
        current_user_id,
        item_id,
        body.permission,
        password=body.password,
        expires_at=body.expires_at,
    )
    await session.commit()
    return result


class LinkTokenResponse(BaseModel):
    token: str


@router.get(
    "/links/{link_id}/token",
    response_model=LinkTokenResponse,
    summary="Reveal a share link's token so the owner can copy the URL again",
)
async def reveal_link_token(
    link_id: UUID,
    current_user_id: CurrentUserId,
    service: LinkServiceDep,
) -> LinkTokenResponse:
    """Owner-only, and only on demand — see design §6.12.11 rule 3a."""
    return LinkTokenResponse(token=await service.reveal_token(current_user_id, link_id))


@router.delete(
    "/links/{link_id}/record",
    status_code=204,
    summary="Delete a dead share link's record",
)
async def delete_link_record(
    link_id: UUID,
    current_user_id: CurrentUserId,
    service: LinkServiceDep,
    session: DbSession,
) -> None:
    await service.delete_link_record(current_user_id, link_id)
    await session.commit()


@router.delete(
    "/links/{link_id}",
    status_code=204,
    summary="Deactivate a share link",
)
async def deactivate_link(
    link_id: UUID,
    current_user_id: CurrentUserId,
    service: LinkServiceDep,
    session: DbSession,
) -> None:
    await service.deactivate_link(current_user_id, link_id)
    await session.commit()
