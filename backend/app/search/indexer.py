from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_search_index import FileSearchIndex
from app.search.embedding import EmbeddingClient
from app.search.extract import extract_text
from app.search.semantic import AbstractFileEmbeddingRepository, embeddable_text

logger = logging.getLogger("app.search.indexer")


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

    def __init__(
        self,
        repo: AbstractSearchIndexRepository,
        *,
        embedding_client: EmbeddingClient | None = None,
        embedding_repo: AbstractFileEmbeddingRepository | None = None,
        embedding_model: str = "",
    ) -> None:
        self._repo = repo
        # Optional semantic-search indexing (Ollama embeddings + pgvector).
        self._embedding_client = embedding_client
        self._embedding_repo = embedding_repo
        self._embedding_model = embedding_model

    async def index_file(
        self,
        *,
        item_id: UUID,
        data: bytes,
        mime_type: str | None,
        extension: str | None,
    ) -> bool:
        """Extract and store text for a file. Returns True if content was indexed.
        If nothing is extractable, any stale index rows are removed."""
        text = extract_text(data=data, mime_type=mime_type, extension=extension)
        if text is None:
            await self._repo.delete(item_id)
            await self._delete_embedding(item_id)
            return False
        await self._repo.upsert(item_id=item_id, content=text, updated_at=datetime.now(UTC))
        await self._index_embedding(item_id, text)
        return True

    async def _index_embedding(self, item_id: UUID, text: str) -> None:
        if self._embedding_client is None or self._embedding_repo is None:
            return
        try:
            vector = await self._embedding_client.embed(embeddable_text(text))
            await self._embedding_repo.upsert(
                item_id=item_id,
                embedding=vector,
                model=self._embedding_model,
                updated_at=datetime.now(UTC),
            )
        except Exception:
            # Embedding is best-effort; failures must never break uploads.
            logger.exception("embedding index failed for item %s", item_id)

    async def _delete_embedding(self, item_id: UUID) -> None:
        if self._embedding_repo is None:
            return
        try:
            await self._embedding_repo.delete(item_id)
        except Exception:
            logger.exception("embedding delete failed for item %s", item_id)
