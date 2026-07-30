from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime
from uuid import UUID

from app.activity_log.actions import ActivityAction
from app.activity_log.service import ActivityLogService
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.security import hash_password, verify_password
from app.drive.repository import AbstractDriveItemRepository
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.models.share_link import ShareLink
from app.permission.permissions import LinkPermission, Permission
from app.schemas.common import DriveItemResponse, Page
from app.share.repository import AbstractShareLinkRepository, AbstractShareManagementRepository
from app.share.schemas import (
    SharedByMeEntry,
    SharedByMeLink,
    SharedByMeUserShare,
    ShareLinkResponse,
    ShareResponse,
)
from app.users.service import UserService


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _item_to_response(
    item: DriveItem, *, shared_with_users: bool, has_active_link: bool
) -> DriveItemResponse:
    """Item metadata for a "shared by me" row.

    Starred state is not resolved here — it belongs to the drive listing, and
    fetching it would add a query per page for something this view never shows.
    """
    return DriveItemResponse(
        id=item.id,
        owner_id=item.owner_id,
        parent_id=item.parent_id,
        item_type=item.item_type,
        name=item.name,
        mime_type=item.mime_type,
        extension=item.extension,
        size_bytes=item.size_bytes,
        is_starred=False,
        is_deleted=item.is_deleted,
        deleted_at=item.deleted_at,
        created_by=item.created_by,
        updated_by=item.updated_by,
        created_at=item.created_at,
        updated_at=item.updated_at,
        is_shared_with_users=shared_with_users,
        has_active_public_link=has_active_link,
    )


def _link_live(link: ShareLink, now: datetime) -> bool:
    """A link is usable only while enabled and unexpired."""
    return link.is_active and (link.expires_at is None or link.expires_at > now)


def _share_to_response(share: Share) -> ShareResponse:
    return ShareResponse(
        id=share.id,
        item_id=share.item_id,
        owner_id=share.owner_id,
        target_user_id=share.target_user_id,
        permission=share.permission,
        created_at=share.created_at,
        updated_at=share.updated_at,
    )


def _link_to_response(link: ShareLink, *, token: str | None = None) -> ShareLinkResponse:
    return ShareLinkResponse(
        id=link.id,
        item_id=link.item_id,
        token=token,
        permission=link.permission,
        expires_at=link.expires_at,
        is_active=link.is_active,
        created_by=link.created_by,
        created_at=link.created_at,
    )


class ShareService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        share_repo: AbstractShareManagementRepository,
        user_svc: UserService,
        activity_svc: ActivityLogService | None = None,
    ) -> None:
        self._items = item_repo
        self._shares = share_repo
        self._users = user_svc
        self._activity = activity_svc

    async def _assert_owner(self, user_id: UUID, item_id: UUID) -> None:
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found")
        if item.owner_id != user_id:
            raise ForbiddenError("Only the owner can manage shares")

    async def share_item(
        self, actor_id: UUID, item_id: UUID, target_email: str, permission: Permission
    ) -> ShareResponse:
        await self._assert_owner(actor_id, item_id)
        target = await self._users.get_by_email(target_email)
        if target.id == actor_id:
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot share with yourself")

        existing = await self._shares.get_by_item_and_user(item_id, target.id)
        if existing is not None:
            share = await self._shares.update_permission(existing.id, permission.value)
        else:
            share = await self._shares.create(
                item_id=item_id,
                owner_id=actor_id,
                target_user_id=target.id,
                permission=permission.value,
            )

        if self._activity:
            await self._activity.log(
                actor_id=actor_id, action=ActivityAction.SHARE, item_id=item_id
            )
        return _share_to_response(share)

    async def remove_share(self, actor_id: UUID, item_id: UUID, target_user_id: UUID) -> None:
        await self._assert_owner(actor_id, item_id)
        share = await self._shares.get_by_item_and_user(item_id, target_user_id)
        if share is None:
            raise NotFoundError("Share not found")
        await self._shares.delete(share.id)
        if self._activity:
            await self._activity.log(
                actor_id=actor_id, action=ActivityAction.UNSHARE, item_id=item_id
            )

    async def list_shared_by_me(
        self, user_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> Page[SharedByMeEntry]:
        """What this user has shared out, one entry per item (proposal §29).

        The reverse of "shared with me": without it there is no single place to
        see — or take back — what has been handed out, and a forgotten public
        link can stay live indefinitely.
        """
        offset = (page - 1) * page_size
        rows, total = await self._shares.list_shared_by_me(user_id, offset=offset, limit=page_size)
        now = datetime.now(UTC)
        entries = [
            SharedByMeEntry(
                item=_item_to_response(
                    row.item,
                    shared_with_users=bool(row.shares),
                    has_active_link=any(_link_live(lnk, now) for lnk in row.links),
                ),
                user_shares=[
                    SharedByMeUserShare(
                        target_user_id=share.target_user_id,
                        email=user.email,
                        username=user.username,
                        permission=share.permission,
                        created_at=share.created_at,
                    )
                    for share, user in row.shares
                ],
                links=[
                    SharedByMeLink(
                        link_id=link.id,
                        permission=link.permission,
                        # Never the hash — only whether one exists.
                        has_password=link.password_hash is not None,
                        expires_at=link.expires_at,
                        is_active=_link_live(link, now),
                        created_at=link.created_at,
                    )
                    for link in row.links
                ],
            )
            for row in rows
        ]
        return Page.create(entries, total, page=page, page_size=page_size)

    async def list_shared_with_me(
        self, user_id: UUID, *, page: int = 1, page_size: int = 20
    ) -> Page[ShareResponse]:
        offset = (page - 1) * page_size
        shares, total = await self._shares.list_shared_with_me(
            user_id, offset=offset, limit=page_size
        )
        return Page.create(
            [_share_to_response(s) for s in shares],
            total,
            page=page,
            page_size=page_size,
        )


class ShareLinkService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        link_repo: AbstractShareLinkRepository,
    ) -> None:
        self._items = item_repo
        self._links = link_repo

    async def create_link(
        self,
        actor_id: UUID,
        item_id: UUID,
        permission: LinkPermission,
        *,
        password: str | None = None,
        expires_at: datetime | None = None,
    ) -> ShareLinkResponse:
        item = await self._items.get_by_id(item_id)
        if item is None:
            raise NotFoundError("Item not found")
        if item.owner_id != actor_id:
            raise ForbiddenError("Only the owner can create share links")

        if permission == LinkPermission.EDITOR and expires_at is None:
            # The only time bound an editor link has. A link that lets strangers
            # write and never dies is not something to create by omission.
            raise AppError(
                ErrorCode.INVALID_OPERATION,
                "An editor link must have an expiry date",
                status_code=422,
            )

        token = secrets.token_urlsafe(32)
        token_hash = _hash_token(token)
        # A share password is a user-chosen secret, so it gets a real password
        # hash (salted, constant-time verify) rather than the bare SHA-256 used
        # for the high-entropy token. Design §6.12.11 rule 3.
        password_hash = hash_password(password) if password else None

        link = await self._links.create(
            item_id=item_id,
            token_hash=token_hash,
            permission=permission.value,
            password_hash=password_hash,
            expires_at=expires_at,
            created_by=actor_id,
        )
        return _link_to_response(link, token=token)

    async def validate_access(self, token: str, *, password: str | None = None) -> ShareLink:
        token_hash = _hash_token(token)
        link = await self._links.get_by_token_hash(token_hash)
        if link is None:
            raise NotFoundError("Share link not found")
        if not link.is_active:
            raise AppError(ErrorCode.INVALID_OPERATION, "Share link has been disabled")
        if link.expires_at is not None and link.expires_at < datetime.now(UTC):
            raise AppError(ErrorCode.INVALID_OPERATION, "Share link has expired")
        if link.password_hash is not None and (
            password is None or not verify_password(password, link.password_hash)
        ):
            raise ForbiddenError("Invalid password")
        return link

    async def _owned_link(self, actor_id: UUID, link_id: UUID) -> ShareLink:
        link = await self._links.get_by_id(link_id)
        if link is None:
            raise NotFoundError("Share link not found")
        item = await self._items.get_by_id(link.item_id)
        if item is None or item.owner_id != actor_id:
            raise ForbiddenError("Only the owner can manage share links")
        return link

    async def delete_link_record(self, actor_id: UUID, link_id: UUID) -> None:
        """Remove a public link outright (proposal §29.2 rule 4.1).

        Live links included: deleting the row *is* the revocation — the token
        lookup and every credential check resolve through it, so access stops
        immediately. There is no undo and no separate "disable" step in front
        of it (proposal §29.5 decision 4, revised 2026-07-27).
        """
        await self._owned_link(actor_id, link_id)
        await self._links.delete(link_id)

    async def deactivate_link(self, actor_id: UUID, link_id: UUID) -> None:
        # The old comment here claimed the router checked ownership; it never
        # did, so any signed-in user could kill any link they knew the id of.
        await self._owned_link(actor_id, link_id)
        await self._links.deactivate(link_id)
