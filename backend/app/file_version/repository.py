from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_version import FileVersion


class AbstractFileVersionRepository(ABC):
    @abstractmethod
    async def create(
        self,
        *,
        file_id: UUID,
        version_no: int,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None,
        created_by: UUID,
    ) -> FileVersion: ...

    @abstractmethod
    async def get_max_version_no(self, file_id: UUID) -> int: ...

    @abstractmethod
    async def list_by_file(self, file_id: UUID) -> list[FileVersion]: ...


class SQLFileVersionRepository(AbstractFileVersionRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        file_id: UUID,
        version_no: int,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None,
        created_by: UUID,
    ) -> FileVersion:
        version = FileVersion(
            id=uuid4(),
            file_id=file_id,
            version_no=version_no,
            storage_key=storage_key,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._session.add(version)
        await self._session.flush()
        return version

    async def get_max_version_no(self, file_id: UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(FileVersion.version_no), 0)).where(
                FileVersion.file_id == file_id
            )
        )
        return int(result.scalar_one())

    async def list_by_file(self, file_id: UUID) -> list[FileVersion]:
        result = await self._session.execute(
            select(FileVersion)
            .where(FileVersion.file_id == file_id)
            .order_by(FileVersion.version_no.desc())
        )
        return list(result.scalars().all())
