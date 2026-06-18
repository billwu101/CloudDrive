from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.file_embedding import FileEmbedding
from app.models.file_search_index import FileSearchIndex
from app.search.embedding import EmbeddingClient
from app.search.semantic import AbstractFileEmbeddingRepository, embeddable_text


@dataclass(frozen=True)
class BackfillResult:
    indexed: int  # embeddings produced in this run
    remaining: int  # files still missing an embedding afterwards


class AbstractEmbeddingBackfillRepository(ABC):
    @abstractmethod
    async def list_pending(self, *, user_id: UUID, limit: int) -> list[tuple[UUID, str]]:
        """(item_id, content) for the user's files that have indexed text but no
        embedding yet."""

    @abstractmethod
    async def count_pending(self, *, user_id: UUID) -> int: ...


class SQLEmbeddingBackfillRepository(AbstractEmbeddingBackfillRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_pending(self, *, user_id: UUID, limit: int) -> list[tuple[UUID, str]]:
        stmt = (
            select(FileSearchIndex.item_id, FileSearchIndex.content)
            .join(DriveItem, DriveItem.id == FileSearchIndex.item_id)
            .outerjoin(FileEmbedding, FileEmbedding.item_id == FileSearchIndex.item_id)
            .where(
                DriveItem.owner_id == user_id,
                DriveItem.is_deleted.is_(False),
                FileEmbedding.item_id.is_(None),
            )
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def count_pending(self, *, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(FileSearchIndex)
            .join(DriveItem, DriveItem.id == FileSearchIndex.item_id)
            .outerjoin(FileEmbedding, FileEmbedding.item_id == FileSearchIndex.item_id)
            .where(
                DriveItem.owner_id == user_id,
                DriveItem.is_deleted.is_(False),
                FileEmbedding.item_id.is_(None),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())


class EmbeddingBackfillService:
    """Backfills embeddings for files indexed before semantic search was enabled
    (or while it was off). Processes one capped batch per call so it can be driven
    repeatedly until ``remaining`` reaches 0."""

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClient,
        backfill_repo: AbstractEmbeddingBackfillRepository,
        embedding_repo: AbstractFileEmbeddingRepository,
        model: str,
    ) -> None:
        self._client = embedding_client
        self._backfill = backfill_repo
        self._embedding = embedding_repo
        self._model = model

    async def run(self, *, user_id: UUID, batch_size: int = 50) -> BackfillResult:
        pending = await self._backfill.list_pending(user_id=user_id, limit=batch_size)
        indexed = 0
        for item_id, content in pending:
            # Fail fast: an embedding error here means the service is down, so
            # there's no point hammering the rest of the batch.
            vector = await self._client.embed(embeddable_text(content))
            await self._embedding.upsert(
                item_id=item_id,
                embedding=vector,
                model=self._model,
                updated_at=datetime.now(UTC),
            )
            indexed += 1
        remaining = await self._backfill.count_pending(user_id=user_id)
        return BackfillResult(indexed=indexed, remaining=remaining)
