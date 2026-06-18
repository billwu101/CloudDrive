from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_search_index import FileSearchIndex
from app.search.extract import extract_text


class AbstractSearchIndexRepository(ABC):
    @abstractmethod
    async def upsert(self, *, item_id: UUID, content: str, updated_at: datetime) -> None: ...

    @abstractmethod
    async def delete(self, item_id: UUID) -> None: ...


class SQLSearchIndexRepository(AbstractSearchIndexRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, *, item_id: UUID, content: str, updated_at: datetime) -> None:
        stmt = pg_insert(FileSearchIndex).values(
            item_id=item_id, content=content, updated_at=updated_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[FileSearchIndex.item_id],
            set_={"content": content, "updated_at": updated_at},
        )
        await self._session.execute(stmt)

    async def delete(self, item_id: UUID) -> None:
        index = await self._session.get(FileSearchIndex, item_id)
        if index is not None:
            await self._session.delete(index)


class SearchIndexService:
    """Maintains the full-text content index for files.

    Extraction failures and unsupported types are non-fatal: the file simply
    isn't content-searchable (it's still findable by name).
    """

    def __init__(self, repo: AbstractSearchIndexRepository) -> None:
        self._repo = repo

    async def index_file(
        self,
        *,
        item_id: UUID,
        data: bytes,
        mime_type: str | None,
        extension: str | None,
    ) -> bool:
        """Extract and store text for a file. Returns True if content was indexed.
        If nothing is extractable, any stale index row is removed."""
        text = extract_text(data=data, mime_type=mime_type, extension=extension)
        if text is None:
            await self._repo.delete(item_id)
            return False
        await self._repo.upsert(item_id=item_id, content=text, updated_at=datetime.now(UTC))
        return True
