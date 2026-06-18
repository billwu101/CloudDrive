from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.file_embedding import FileEmbedding
from app.models.share import Share
from app.search.embedding import EmbeddingClient, EmbeddingError

logger = logging.getLogger("app.search.semantic")

# Cap how much text we embed — embedding models have a context limit and the
# leading content is usually enough to capture a document's topic.
EMBED_INPUT_CHARS = 8_000


@dataclass(frozen=True)
class SemanticHit:
    item: DriveItem
    score: float  # cosine similarity in [-1, 1]; higher = more similar


class AbstractFileEmbeddingRepository(ABC):
    @abstractmethod
    async def upsert(
        self, *, item_id: UUID, embedding: list[float], model: str, updated_at: datetime
    ) -> None: ...

    @abstractmethod
    async def delete(self, item_id: UUID) -> None: ...

    @abstractmethod
    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float]]:
        """Nearest items by cosine distance. Returns (item, distance) ascending."""


class SQLFileEmbeddingRepository(AbstractFileEmbeddingRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(
        self, *, item_id: UUID, embedding: list[float], model: str, updated_at: datetime
    ) -> None:
        stmt = pg_insert(FileEmbedding).values(
            item_id=item_id, embedding=embedding, model=model, updated_at=updated_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[FileEmbedding.item_id],
            set_={"embedding": embedding, "model": model, "updated_at": updated_at},
        )
        await self._session.execute(stmt)

    async def delete(self, item_id: UUID) -> None:
        row = await self._session.get(FileEmbedding, item_id)
        if row is not None:
            await self._session.delete(row)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float]]:
        shared_subq = select(Share.item_id).where(Share.target_user_id == user_id)
        distance = FileEmbedding.embedding.cosine_distance(query).label("distance")
        stmt = (
            select(DriveItem, distance)
            .join(FileEmbedding, FileEmbedding.item_id == DriveItem.id)
            .where(
                DriveItem.is_deleted.is_(False),
                or_(DriveItem.owner_id == user_id, DriveItem.id.in_(shared_subq)),
            )
            .order_by(distance)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]


class SemanticSearchService:
    """Embed the query and return the nearest files by cosine similarity."""

    def __init__(
        self, *, embedding_client: EmbeddingClient, repo: AbstractFileEmbeddingRepository
    ) -> None:
        self._client = embedding_client
        self._repo = repo

    async def search(self, *, user_id: UUID, query: str, limit: int = 20) -> list[SemanticHit]:
        query = query.strip()
        if not query:
            return []
        vector = await self._client.embed(query)  # raises EmbeddingError if unavailable
        rows = await self._repo.semantic_search(user_id=user_id, query=vector, limit=limit)
        # cosine distance d in [0, 2]; similarity = 1 - d.
        return [SemanticHit(item=item, score=1.0 - distance) for item, distance in rows]


def embeddable_text(text: str) -> str:
    """Trim extracted text to what we actually embed."""
    return text[:EMBED_INPUT_CHARS]


__all__ = [
    "AbstractFileEmbeddingRepository",
    "EmbeddingError",
    "SQLFileEmbeddingRepository",
    "SemanticHit",
    "SemanticSearchService",
    "embeddable_text",
]
