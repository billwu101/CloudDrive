from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.activity_log.actions import ActivityAction
from app.activity_log.service import ActivityLogService
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppError,
    FileTooLargeError,
    InvalidOperationError,
    NotFoundError,
)
from app.drive.repository import AbstractDriveItemRepository
from app.drive.schemas import ItemType
from app.file_version.repository import AbstractFileVersionRepository
from app.models.drive_item import DriveItem
from app.models.upload_session import UploadChunk, UploadSession
from app.permission.service import PermissionService
from app.schemas.common import DriveItemResponse
from app.storage.base import UPLOAD_TEMP_PREFIX, StorageProvider
from app.upload.service import _make_storage_key, _safe_filename, _split_name, _to_response
from app.upload.session_repository import AbstractUploadSessionRepository
from app.users.service import QuotaService

# Sessions in these states no longer accept chunks or completion.
TERMINAL_STATUSES = frozenset({"completed", "failed", "cancelled"})


@dataclass(frozen=True)
class UploadSessionStatus:
    """A session plus the chunk indexes already stored, for resuming."""

    session: UploadSession
    uploaded_chunks: list[int]


def _chunk_key(user_id: UUID, session_id: UUID, chunk_index: int) -> str:
    return f"{UPLOAD_TEMP_PREFIX}/{user_id}/{session_id}/{chunk_index}"


class UploadSessionService:
    """Chunked resumable upload (proposal §27, detailed-design §6.7.7).

    Memory use is independent of file size throughout: chunks stream to
    storage on arrival, and completion merges them through a fixed buffer.
    """

    def __init__(
        self,
        session_repo: AbstractUploadSessionRepository,
        item_repo: AbstractDriveItemRepository,
        version_repo: AbstractFileVersionRepository,
        storage: StorageProvider,
        permission_svc: PermissionService,
        quota_svc: QuotaService,
        activity_svc: ActivityLogService | None = None,
        *,
        chunk_size: int,
        max_file_size: int,
        retention_days: int,
    ) -> None:
        self._sessions = session_repo
        self._items = item_repo
        self._versions = version_repo
        self._storage = storage
        self._perm = permission_svc
        self._quota = quota_svc
        self._activity = activity_svc
        self._chunk_size = chunk_size
        self._max_file_size = max_file_size
        self._retention_days = retention_days

    async def _get_or_404(self, user_id: UUID, session_id: UUID) -> UploadSession:
        """Another user's session is reported as missing, not forbidden, so
        session ids cannot be probed for existence."""
        session = await self._sessions.get_for_user(session_id, user_id)
        if session is None:
            raise NotFoundError("Upload session not found")
        return session

    async def create_session(
        self,
        user_id: UUID,
        *,
        filename: str,
        total_size: int,
        parent_id: UUID | None = None,
        mime_type: str | None = None,
    ) -> UploadSessionStatus:
        filename = _safe_filename(filename)
        if total_size > self._max_file_size:
            raise FileTooLargeError(
                f"File exceeds the maximum upload size of {self._max_file_size} bytes"
            )

        if parent_id is not None:
            parent = await self._items.get_by_id(parent_id)
            if parent is None or parent.is_deleted:
                raise NotFoundError("Parent folder not found")
            if parent.item_type != ItemType.FOLDER:
                raise AppError(ErrorCode.INVALID_OPERATION, "Parent must be a folder")
            await self._perm.assert_can_edit(user_id, parent)

        # Space already promised to the user's other unfinished sessions counts
        # against them, so several large uploads opened at once cannot jointly
        # oversell the quota and all fail at the very end.
        reserved = await self._sessions.sum_active_total_size(user_id)
        await self._quota.assert_has_space(user_id, total_size + reserved)

        now = datetime.now(UTC)
        # Ceiling division; a zero-byte file legitimately has no chunks.
        total_chunks = -(-total_size // self._chunk_size)
        session = await self._sessions.create(
            user_id=user_id,
            parent_id=parent_id,
            filename=filename,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=self._chunk_size,
            total_chunks=total_chunks,
            expires_at=now + timedelta(days=self._retention_days),
            now=now,
        )
        return UploadSessionStatus(session=session, uploaded_chunks=[])

    async def get_session(self, user_id: UUID, session_id: UUID) -> UploadSessionStatus:
        session = await self._get_or_404(user_id, session_id)
        indexes = await self._sessions.list_completed_indexes(session.id)
        return UploadSessionStatus(session=session, uploaded_chunks=indexes)

    async def upload_chunk(
        self,
        user_id: UUID,
        session_id: UUID,
        chunk_index: int,
        stream: AsyncIterator[bytes],
    ) -> None:
        session = await self._get_or_404(user_id, session_id)
        if session.status in TERMINAL_STATUSES:
            raise InvalidOperationError(f"Upload session is already {session.status}")
        if chunk_index < 0 or chunk_index >= session.total_chunks:
            raise InvalidOperationError("Chunk index out of range")

        key = _chunk_key(user_id, session.id, chunk_index)
        sha = hashlib.sha256()

        async def _hashing_stream() -> AsyncIterator[bytes]:
            async for chunk in stream:
                sha.update(chunk)
                yield chunk

        # Overwrites any earlier attempt at this index, which is what makes a
        # retry of a half-sent chunk safe.
        size = await self._storage.save_stream(key, _hashing_stream())

        now = datetime.now(UTC)
        await self._sessions.upsert_chunk(
            session_id=session.id,
            chunk_index=chunk_index,
            size=size,
            storage_key=key,
            checksum_sha256=sha.hexdigest(),
            now=now,
        )
        if session.status == "pending":
            await self._sessions.update_status(session.id, "uploading", now=now)

    async def complete_session(self, user_id: UUID, session_id: UUID) -> DriveItemResponse:
        session = await self._get_or_404(user_id, session_id)
        if session.status in TERMINAL_STATUSES:
            raise InvalidOperationError(f"Upload session is already {session.status}")

        chunks = await self._sessions.list_chunks(session.id)
        present = {c.chunk_index for c in chunks}
        missing = [i for i in range(session.total_chunks) if i not in present]
        if missing:
            # Deliberately not a terminal state: the client can send the gaps
            # and call complete again, which is the whole point of resuming.
            raise InvalidOperationError(f"Upload is incomplete: {len(missing)} chunk(s) missing")

        ordered = sorted(chunks, key=lambda c: c.chunk_index)
        storage_key = _make_storage_key(user_id, uuid4())
        actual_size = await self._storage.concat([c.storage_key for c in ordered], storage_key)

        try:
            checksum = await self._checksum_of(storage_key)
            item = await self._create_item(session, user_id, storage_key, actual_size, checksum)
        except Exception:
            # The merged blob is not referenced by anything yet, so drop it
            # rather than leave an orphan behind (§7.9 compensating rollback).
            await self._storage.delete(storage_key)
            raise

        await self._discard_chunks(ordered)
        await self._sessions.update_status(
            session.id,
            "completed",
            now=datetime.now(UTC),
            checksum_sha256=checksum,
            drive_item_id=item.id,
        )

        if self._activity is not None:
            await self._activity.log(
                actor_id=user_id,
                action=ActivityAction.UPLOAD,
                item_id=item.id,
                metadata={"session_id": str(session.id), "chunked": True},
            )
        return _to_response(item)

    async def cancel_session(self, user_id: UUID, session_id: UUID) -> None:
        session = await self._get_or_404(user_id, session_id)
        if session.status == "completed":
            raise InvalidOperationError("Upload session is already completed")
        if session.status == "cancelled":
            return

        await self._discard_chunks(await self._sessions.list_chunks(session.id))
        # Cancelling never touched used_bytes, so there is no quota to give back.
        await self._sessions.update_status(session.id, "cancelled", now=datetime.now(UTC))

    async def cleanup_expired(self) -> int:
        """Reclaim sessions past their retention window, chunks included."""
        expired = await self._sessions.list_expired(datetime.now(UTC))
        for session in expired:
            await self._discard_chunks(await self._sessions.list_chunks(session.id))
            await self._sessions.delete_session(session.id)
        return len(expired)

    async def _checksum_of(self, storage_key: str) -> str:
        """Hash the merged object by streaming it, never holding it in memory."""
        sha = hashlib.sha256()
        async for chunk in self._storage.open_read(storage_key):
            sha.update(chunk)
        return sha.hexdigest()

    async def _create_item(
        self,
        session: UploadSession,
        user_id: UUID,
        storage_key: str,
        actual_size: int,
        checksum: str,
    ) -> DriveItem:
        stem, ext = _split_name(session.filename)
        # Same-folder deduplication happens now, not at session creation, so a
        # long upload does not reserve a name it might not need.
        final_name = session.filename
        counter = 1
        while await self._items.name_exists_in_parent(final_name, session.parent_id, user_id):
            final_name = f"{stem} ({counter}){ext}"
            counter += 1

        item = await self._items.create(
            owner_id=user_id,
            parent_id=session.parent_id,
            item_type=ItemType.FILE,
            name=final_name,
            created_by=user_id,
        )
        item.size_bytes = actual_size
        item.mime_type = session.mime_type
        item.extension = ext.lstrip(".") if ext else None
        item.checksum_sha256 = checksum
        item.storage_key = storage_key

        await self._versions.create(
            file_id=item.id,
            version_no=1,
            storage_key=storage_key,
            size_bytes=actual_size,
            checksum_sha256=checksum,
            created_by=user_id,
        )
        # Quota is only spent once the file really exists.
        await self._quota.add_used_bytes(user_id, actual_size)
        return item

    async def _discard_chunks(self, chunks: list[UploadChunk]) -> None:
        """Remove chunk blobs and their rows. Called on completion, on cancel
        and on expiry, so temporary chunks never outlive their session."""
        if not chunks:
            return
        for chunk in chunks:
            await self._storage.delete(chunk.storage_key)
        await self._sessions.delete_chunks(chunks[0].session_id)
