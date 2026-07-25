from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.upload_session import UploadChunk, UploadSession

# Sessions in these states are still in flight; anything else is terminal.
ACTIVE_STATUSES = ("pending", "uploading")


class AbstractUploadSessionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        user_id: UUID,
        parent_id: UUID | None,
        filename: str,
        mime_type: str | None,
        total_size: int,
        chunk_size: int,
        total_chunks: int,
        expires_at: datetime,
        now: datetime,
    ) -> UploadSession: ...

    @abstractmethod
    async def get_for_user(self, session_id: UUID, user_id: UUID) -> UploadSession | None: ...

    @abstractmethod
    async def list_completed_indexes(self, session_id: UUID) -> list[int]: ...

    @abstractmethod
    async def list_chunks(self, session_id: UUID) -> list[UploadChunk]: ...

    @abstractmethod
    async def upsert_chunk(
        self,
        *,
        session_id: UUID,
        chunk_index: int,
        size: int,
        storage_key: str,
        checksum_sha256: str | None,
        now: datetime,
    ) -> None: ...

    @abstractmethod
    async def update_status(
        self,
        session_id: UUID,
        status: str,
        *,
        now: datetime,
        checksum_sha256: str | None = None,
        drive_item_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None: ...

    @abstractmethod
    async def sum_active_total_size(
        self, user_id: UUID, *, exclude_session_id: UUID | None = None
    ) -> int: ...

    @abstractmethod
    async def list_expired(self, now: datetime) -> list[UploadSession]: ...

    @abstractmethod
    async def delete_chunks(self, session_id: UUID) -> None: ...

    @abstractmethod
    async def delete_session(self, session_id: UUID) -> None: ...


class SQLUploadSessionRepository(AbstractUploadSessionRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        user_id: UUID,
        parent_id: UUID | None,
        filename: str,
        mime_type: str | None,
        total_size: int,
        chunk_size: int,
        total_chunks: int,
        expires_at: datetime,
        now: datetime,
    ) -> UploadSession:
        session = UploadSession(
            id=uuid4(),
            user_id=user_id,
            parent_id=parent_id,
            filename=filename,
            mime_type=mime_type,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            status="pending",
            created_at=now,
            updated_at=now,
            expires_at=expires_at,
        )
        self._session.add(session)
        await self._session.flush()
        return session

    async def get_for_user(self, session_id: UUID, user_id: UUID) -> UploadSession | None:
        # Scoped by user_id so another user's session is indistinguishable from
        # one that does not exist.
        result = await self._session.execute(
            select(UploadSession).where(
                UploadSession.id == session_id, UploadSession.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def list_completed_indexes(self, session_id: UUID) -> list[int]:
        result = await self._session.execute(
            select(UploadChunk.chunk_index)
            .where(UploadChunk.session_id == session_id)
            .order_by(UploadChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def list_chunks(self, session_id: UUID) -> list[UploadChunk]:
        result = await self._session.execute(
            select(UploadChunk)
            .where(UploadChunk.session_id == session_id)
            .order_by(UploadChunk.chunk_index)
        )
        return list(result.scalars().all())

    async def upsert_chunk(
        self,
        *,
        session_id: UUID,
        chunk_index: int,
        size: int,
        storage_key: str,
        checksum_sha256: str | None,
        now: datetime,
    ) -> None:
        # Re-sending a chunk must be safe, so the unique (session, index) pair
        # updates in place instead of erroring.
        stmt = (
            pg_insert(UploadChunk)
            .values(
                id=uuid4(),
                session_id=session_id,
                chunk_index=chunk_index,
                size=size,
                storage_key=storage_key,
                checksum_sha256=checksum_sha256,
                created_at=now,
            )
            .on_conflict_do_update(
                index_elements=[UploadChunk.session_id, UploadChunk.chunk_index],
                set_={
                    "size": size,
                    "storage_key": storage_key,
                    "checksum_sha256": checksum_sha256,
                    "created_at": now,
                },
            )
        )
        await self._session.execute(stmt)

    async def update_status(
        self,
        session_id: UUID,
        status: str,
        *,
        now: datetime,
        checksum_sha256: str | None = None,
        drive_item_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None:
        result = await self._session.execute(
            select(UploadSession).where(UploadSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if session is None:
            return
        session.status = status
        session.updated_at = now
        if checksum_sha256 is not None:
            session.checksum_sha256 = checksum_sha256
        if drive_item_id is not None:
            session.drive_item_id = drive_item_id
        if error_code is not None:
            session.error_code = error_code
        await self._session.flush()

    async def sum_active_total_size(
        self, user_id: UUID, *, exclude_session_id: UUID | None = None
    ) -> int:
        # Space already promised to other in-flight sessions, so two large
        # uploads opened at once cannot jointly oversell the quota.
        stmt = select(UploadSession.total_size).where(
            UploadSession.user_id == user_id,
            UploadSession.status.in_(ACTIVE_STATUSES),
        )
        if exclude_session_id is not None:
            stmt = stmt.where(UploadSession.id != exclude_session_id)
        result = await self._session.execute(stmt)
        return sum(result.scalars().all())

    async def list_expired(self, now: datetime) -> list[UploadSession]:
        result = await self._session.execute(
            select(UploadSession).where(
                UploadSession.expires_at < now,
                UploadSession.status.in_(ACTIVE_STATUSES),
            )
        )
        return list(result.scalars().all())

    async def delete_chunks(self, session_id: UUID) -> None:
        await self._session.execute(delete(UploadChunk).where(UploadChunk.session_id == session_id))

    async def delete_session(self, session_id: UUID) -> None:
        await self._session.execute(delete(UploadSession).where(UploadSession.id == session_id))
