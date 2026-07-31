"""Guest-side logic for public share links (proposal §28, design §6.12.8-11).

This is the only unauthenticated path in the backend, so every rule here exists
to stop it becoming a way to enumerate links, brute-force passwords, or reach
items outside the shared subtree.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError
from app.core.mime import resolve_mime
from app.core.security import (
    ShareAccessClaims,
    create_share_access_token,
    decode_share_access_token,
    hash_password,
    verify_password,
)
from app.download.service import ArchiveResult, DownloadFileResult, DownloadService
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import DriveItemSortField, ItemType
from app.drive.service import DriveService
from app.models.drive_item import DriveItem
from app.permission.permissions import LinkPermission
from app.preview.service import PreviewService, resolve_preview_type
from app.public_share.schemas import PublicItemResponse, PublicSessionResponse
from app.schemas.common import Page, SortOrder
from app.share.repository import AbstractShareLinkRepository
from app.storage.base import StorageProvider
from app.trash.service import TrashService
from app.upload.service import UploadService

# Guard against a cycle in parent_id turning the ancestor walk into an infinite
# loop. Real drives are nowhere near this deep.
_MAX_DEPTH = 64

# Cost-matched dummy hash. Verifying against this when a token is unknown keeps
# "no such link" and "wrong password" in the same timing band, so an attacker
# cannot tell them apart by how long the request took (design §6.12.11 rule 1).
_DUMMY_PASSWORD_HASH = hash_password("timing-equalisation-placeholder")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _invalid() -> AppError:
    """The single response shared by every failure mode.

    Unknown token, wrong password, disabled link and expired link all land
    here: distinguishing them would let a caller probe for valid tokens
    (proposal §28.3 rule 1, §28.5 criterion 5).
    """
    return AppError(
        ErrorCode.SHARE_LINK_INVALID,
        "Link is invalid or no longer available",
        status_code=404,
    )


def _password_required() -> AppError:
    return AppError(
        ErrorCode.SHARE_LINK_PASSWORD_REQUIRED,
        "This link is password protected",
        status_code=401,
    )


def _to_public_item(item: DriveItem) -> PublicItemResponse:
    return PublicItemResponse(
        id=item.id,
        name=item.name,
        item_type=ItemType(item.item_type),
        mime_type=item.mime_type,
        size_bytes=item.size_bytes,
        extension=item.extension,
        preview_type=resolve_preview_type(item),
        updated_at=item.updated_at,
    )


@dataclass(frozen=True)
class AuditContext:
    """The two facts an audit row needs about an anonymous write."""

    owner_id: UUID
    link_id: UUID


@dataclass
class _Authorized:
    """A validated credential plus the live link and root item behind it."""

    claims: ShareAccessClaims
    root: DriveItem
    permission: LinkPermission


class PublicShareService:
    def __init__(
        self,
        item_repo: AbstractDriveItemRepository,
        link_repo: AbstractShareLinkRepository,
        storage: StorageProvider,
        preview_svc: PreviewService,
        download_svc: DownloadService,
        drive_svc: DriveService | None = None,
        upload_svc: UploadService | None = None,
        trash_svc: TrashService | None = None,
    ) -> None:
        self._items = item_repo
        self._links = link_repo
        self._storage = storage
        self._preview = preview_svc
        self._download = download_svc
        # Only the write paths need these; read-only callers (and their tests)
        # can leave them out.
        self._drive_svc = drive_svc
        self._upload_svc = upload_svc
        self._trash_svc = trash_svc

    @property
    def _drive(self) -> DriveService:
        if self._drive_svc is None:  # pragma: no cover - wiring error
            raise RuntimeError("PublicShareService was built without a DriveService")
        return self._drive_svc

    @property
    def _upload(self) -> UploadService:
        if self._upload_svc is None:  # pragma: no cover - wiring error
            raise RuntimeError("PublicShareService was built without an UploadService")
        return self._upload_svc

    @property
    def _trash(self) -> TrashService:
        if self._trash_svc is None:  # pragma: no cover - wiring error
            raise RuntimeError("PublicShareService was built without a TrashService")
        return self._trash_svc

    # --- session ----------------------------------------------------------

    async def open_session(self, token: str, password: str | None) -> PublicSessionResponse:
        settings = get_settings()
        now = datetime.now(UTC)
        link = await self._links.get_by_token_hash(_hash_token(token))

        if link is None:
            # Burn the same work a real password check would, then fail the
            # same way. Without this, response time alone reveals whether the
            # token exists.
            verify_password(password or "", _DUMMY_PASSWORD_HASH)
            raise _invalid()

        if link.locked_until is not None and link.locked_until > now:
            raise _invalid()

        if not link.is_active or (link.expires_at is not None and link.expires_at < now):
            raise _invalid()

        if link.password_hash is not None:
            if password is None:
                # The normal first request of the flow in proposal §28.4, not a
                # failed attempt — so it neither counts against the rate limit
                # nor returns the generic error. This does reveal that the
                # token exists and is password protected; that is inherent to
                # showing a password form at all, and the token's 256 bits of
                # entropy make enumeration infeasible.
                raise _password_required()
            await self._register_attempt(link.id, link.attempt_window_start, link.attempt_count)
            if not verify_password(password, link.password_hash):
                raise _invalid()

        access_token = create_share_access_token(
            link_id=link.id,
            root_item_id=link.item_id,
            permission=link.permission,
        )
        root = await self._items.get_by_id(link.item_id)
        if root is None or root.is_deleted:
            # The shared item was deleted out from under the link.
            raise _invalid()
        return PublicSessionResponse(
            access_token=access_token,
            expires_in=settings.share_access_token_expire_minutes * 60,
            permission=link.permission,
            item=_to_public_item(root),
        )

    async def refresh_session(self, access_token: str) -> PublicSessionResponse:
        """Extend an already-validated session without re-entering the password.

        Refresh only prolongs a state the caller already earned; it never
        re-authorises, and it cannot outrun the total lifetime cap.
        """
        settings = get_settings()
        auth = await self._authorize(access_token)
        cap = auth.claims.chain_started_at + timedelta(
            minutes=settings.share_access_token_max_lifetime_minutes
        )
        if datetime.now(UTC) >= cap:
            raise _invalid()

        token = create_share_access_token(
            link_id=auth.claims.link_id,
            root_item_id=auth.claims.root_item_id,
            permission=auth.claims.permission,
            chain_started_at=auth.claims.chain_started_at,
        )
        return PublicSessionResponse(
            access_token=token,
            expires_in=settings.share_access_token_expire_minutes * 60,
            permission=auth.claims.permission,
            item=_to_public_item(auth.root),
        )

    async def _register_attempt(
        self, link_id: UUID, window_start: datetime | None, count: int
    ) -> None:
        """Count one validation attempt, locking the link once over the limit.

        Kept in the database rather than in process memory: several uvicorn
        workers each holding their own counter would multiply the limit by the
        worker count (design §6.12.11 rule 6).
        """
        settings = get_settings()
        now = datetime.now(UTC)
        if window_start is None or now - window_start >= timedelta(minutes=1):
            window_start, count = now, 0
        count += 1
        locked_until = (
            now + timedelta(minutes=settings.share_link_lockout_minutes)
            if count > settings.share_link_attempt_limit
            else None
        )
        await self._links.update_attempt_state(
            link_id, window_start=window_start, count=count, locked_until=locked_until
        )
        if locked_until is not None:
            raise _invalid()

    # --- authorisation ----------------------------------------------------

    async def _authorize(self, access_token: str) -> _Authorized:
        """Turn a credential into live authorisation, re-checking the link.

        The credential is deliberately not trusted on its own: proposal §28.3
        rule 5 requires the link's state to be re-read on *every* request, so
        that disabling a link takes effect immediately instead of when the
        last credential happens to expire.
        """
        try:
            claims = decode_share_access_token(access_token)
        except AppError as exc:  # any decode failure is simply "invalid"
            raise _invalid() from exc

        link = await self._links.get_by_id(claims.link_id)
        now = datetime.now(UTC)
        if link is None or not link.is_active:
            raise _invalid()
        if link.expires_at is not None and link.expires_at < now:
            raise _invalid()
        # Permission comes from the link as it stands now, never from the
        # credential alone and never from "the creator owns this item"
        # (proposal §28.3 rule 4).
        root = await self._items.get_by_id(link.item_id)
        if root is None or root.is_deleted:
            raise _invalid()
        return _Authorized(claims=claims, root=root, permission=LinkPermission(link.permission))

    async def _resolve_in_subtree(self, auth: _Authorized, item_id: UUID) -> DriveItem:
        """Fetch an item, refusing anything outside the shared subtree.

        Returns 404 rather than 403 for outsiders: a 403 would confirm the id
        exists (proposal §28.3 rule 4).
        """
        item = await self._items.get_by_id(item_id)
        if item is None or item.is_deleted:
            raise _invalid()

        current: DriveItem | None = item
        for _ in range(_MAX_DEPTH):
            if current is None:
                break
            if current.id == auth.root.id:
                return item
            if current.parent_id is None:
                break
            current = await self._items.get_by_id(current.parent_id)
        raise _invalid()

    @staticmethod
    def _assert_can_download(auth: _Authorized) -> None:
        if auth.permission == LinkPermission.VIEWER:
            raise ForbiddenError("This link does not allow downloads")

    @staticmethod
    def _assert_can_edit(auth: _Authorized) -> None:
        """The only thing standing between a guest and owner-level access.

        Every write below runs downstream as `root.owner_id` — the sole identity
        the existing services accept — which is *more* than editor. So the limit
        cannot be delegated: it has to be checked here, on every write path,
        before anything is called. The downstream permission check is a no-op in
        this context, not a second line of defence (design §6.12.11b).
        """
        if auth.permission != LinkPermission.EDITOR:
            raise ForbiddenError("This link does not allow editing")

    # --- content ----------------------------------------------------------

    async def get_root(self, access_token: str) -> PublicItemResponse:
        auth = await self._authorize(access_token)
        return _to_public_item(auth.root)

    async def list_children(
        self, access_token: str, item_id: UUID, *, page: int = 1, page_size: int = 50
    ) -> Page[PublicItemResponse]:
        auth = await self._authorize(access_token)
        folder = await self._resolve_in_subtree(auth, item_id)
        if folder.item_type != ItemType.FOLDER:
            raise AppError(ErrorCode.INVALID_OPERATION, "Not a folder")
        offset = (page - 1) * page_size
        children, total = await self._items.list_children(
            folder.id,
            auth.root.owner_id,
            sort_by=DriveItemSortField.NAME,
            order=SortOrder.ASC,
            offset=offset,
            limit=page_size,
        )
        return Page.create(
            [_to_public_item(c) for c in children], total, page=page, page_size=page_size
        )

    async def preview(
        self, access_token: str, item_id: UUID
    ) -> tuple[str, AsyncGenerator[bytes, None]]:
        """Returns (mime_type, byte stream) for in-browser viewing."""
        auth = await self._authorize(access_token)
        item = await self._resolve_in_subtree(auth, item_id)
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot preview a folder")
        _ptype, mime, stream = await self._preview.content_for_item(item)
        return mime, stream

    async def download(self, access_token: str, item_id: UUID) -> DownloadFileResult:
        auth = await self._authorize(access_token)
        self._assert_can_download(auth)
        item = await self._resolve_in_subtree(auth, item_id)
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot download a folder")
        if not item.storage_key or not await self._storage.exists(item.storage_key):
            raise AppError(
                ErrorCode.ITEM_CONTENT_NOT_FOUND, "File content not found", status_code=404
            )
        return DownloadFileResult(
            filename=item.name,
            mime_type=resolve_mime(
                mime_type=item.mime_type, name=item.name, extension=item.extension
            )
            or "application/octet-stream",
            size_bytes=item.size_bytes,
            stream=self._storage.open_read(item.storage_key),
        )

    # --- writes (editor links only, proposal §33) -------------------------

    async def create_folder(self, access_token: str, parent_id: UUID, name: str) -> DriveItem:
        auth = await self._authorize(access_token)
        self._assert_can_edit(auth)
        parent = await self._resolve_in_subtree(auth, parent_id)
        if parent.item_type != ItemType.FOLDER:
            raise AppError(ErrorCode.INVALID_OPERATION, "Parent must be a folder")
        created = await self._drive.create_folder(auth.root.owner_id, parent.id, name)
        return await self._reload(created.id)

    async def rename(self, access_token: str, item_id: UUID, new_name: str) -> DriveItem:
        auth = await self._authorize(access_token)
        self._assert_can_edit(auth)
        item = await self._resolve_in_subtree(auth, item_id)
        await self._drive.rename(auth.root.owner_id, item.id, new_name)
        return await self._reload(item.id)

    async def move(self, access_token: str, item_id: UUID, new_parent_id: UUID) -> DriveItem:
        auth = await self._authorize(access_token)
        self._assert_can_edit(auth)
        item = await self._resolve_in_subtree(auth, item_id)
        # The destination is checked the same way as the source: a guest must not
        # be able to move content *out* of the subtree they were given.
        parent = await self._resolve_in_subtree(auth, new_parent_id)
        if parent.item_type != ItemType.FOLDER:
            raise AppError(ErrorCode.INVALID_OPERATION, "Destination must be a folder")
        await self._drive.move(auth.root.owner_id, item.id, parent.id)
        return await self._reload(item.id)

    async def trash(self, access_token: str, item_id: UUID) -> None:
        auth = await self._authorize(access_token)
        self._assert_can_edit(auth)
        item = await self._resolve_in_subtree(auth, item_id)
        if item.id == auth.root.id:
            # Trashing the shared root would delete the thing the link points at,
            # leaving the link alive and aimed at nothing.
            raise AppError(ErrorCode.INVALID_OPERATION, "Cannot trash the shared item itself")
        await self._trash.trash_item(auth.root.owner_id, item.id)

    async def upload(
        self,
        access_token: str,
        parent_id: UUID,
        *,
        filename: str,
        stream: AsyncGenerator[bytes, None],
        size_bytes: int,
        mime_type: str | None = None,
    ) -> DriveItem:
        """Upload into a shared folder. Quota is charged to the owner, whose
        drive the file lands in (proposal §33.3 rule 6)."""
        auth = await self._authorize(access_token)
        self._assert_can_edit(auth)
        parent = await self._resolve_in_subtree(auth, parent_id)
        if parent.item_type != ItemType.FOLDER:
            raise AppError(ErrorCode.INVALID_OPERATION, "Uploads need a folder")
        created = await self._upload.upload_simple(
            auth.root.owner_id,
            parent.id,
            filename,
            stream,
            size_bytes,
            mime_type,
        )
        return await self._reload(created.id)

    async def audit_context(self, access_token: str) -> AuditContext:
        """Who a guest write is recorded against, and via which link."""
        auth = await self._authorize(access_token)
        return AuditContext(owner_id=auth.root.owner_id, link_id=auth.claims.link_id)

    async def _reload(self, item_id: UUID) -> DriveItem:
        item = await self._items.get_by_id(item_id)
        if item is None:  # pragma: no cover - written moments ago
            raise _invalid()
        return item

    async def archive(self, access_token: str, item_ids: list[UUID] | None = None) -> ArchiveResult:
        """Zip the shared subtree, or just the items named (proposal §34.4).

        Reuses DownloadService's packer, called as the item's owner: the
        subtree boundary is already fixed by the credential, so the per-file
        owner check inside it is a no-op rather than a second opinion.

        With ``item_ids``, every single one is resolved against the subtree
        first and *any* miss fails the whole request. Packing the valid ones
        and quietly dropping the rest would hand a guest an oracle: ask for a
        known-good id plus a guess, and whether the guess appears in the zip
        tells you if it exists (design §6.12.8).
        """
        auth = await self._authorize(access_token)
        self._assert_can_download(auth)
        if item_ids is None:
            return await self._download.archive(auth.root.owner_id, [auth.root.id])
        if not item_ids:
            raise AppError(ErrorCode.INVALID_OPERATION, "No items selected to download")
        for item_id in item_ids:
            await self._resolve_in_subtree(auth, item_id)
        return await self._download.archive(auth.root.owner_id, item_ids)
