from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_item import DriveItem
from app.models.file_embedding import FileEmbedding
from app.models.share import Share
from app.search.embedding import EmbeddingClient

# Chunking: long documents are split so each part gets its own vector, which
# keeps a single topic from being averaged away across a whole file.
CHUNK_SIZE = 1000  # characters per chunk
CHUNK_OVERLAP = 100  # carried-over characters between adjacent chunks
MAX_CHUNKS = 50  # cap work/storage for very large files
SNIPPET_CHARS = 300  # stored per chunk for the search-result preview


@dataclass(frozen=True)
class ChunkEmbedding:
    index: int
    snippet: str
    vector: list[float]


@dataclass(frozen=True)
class SemanticHit:
    item: DriveItem
    score: float  # cosine similarity in [-1, 1]; higher = more similar
    snippet: str  # text of the best-matching chunk, for preview/highlighting


def chunk_text(text: str, *, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks (capped at MAX_CHUNKS)."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    chunks: list[str] = []
    step = max(1, size - overlap)
    start = 0
    while start < len(text) and len(chunks) < MAX_CHUNKS:
        chunks.append(text[start : start + size])
        start += step
    return chunks


def snippet_of(chunk: str) -> str:
    return chunk[:SNIPPET_CHARS]


class AbstractFileEmbeddingRepository(ABC):
    @abstractmethod
    async def replace_chunks(
        self, *, item_id: UUID, chunks: list[ChunkEmbedding], model: str, updated_at: datetime
    ) -> None:
        """Replace all stored chunk embeddings for a file."""

    @abstractmethod
    async def delete(self, item_id: UUID) -> None: ...

    @abstractmethod
    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float, str]]:
        """Nearest files by their best-matching chunk. Returns
        (item, distance, snippet) ascending by distance."""


class SQLFileEmbeddingRepository(AbstractFileEmbeddingRepository):  # pragma: no cover
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_chunks(
        self, *, item_id: UUID, chunks: list[ChunkEmbedding], model: str, updated_at: datetime
    ) -> None:
        await self.delete(item_id)
        for chunk in chunks:
            self._session.add(
                FileEmbedding(
                    id=uuid4(),
                    item_id=item_id,
                    chunk_index=chunk.index,
                    snippet=chunk.snippet,
                    embedding=chunk.vector,
                    model=model,
                    updated_at=updated_at,
                )
            )
        await self._session.flush()

    async def delete(self, item_id: UUID) -> None:
        rows = await self._session.execute(
            select(FileEmbedding).where(FileEmbedding.item_id == item_id)
        )
        for row in rows.scalars().all():
            await self._session.delete(row)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float, str]]:
        shared_subq = select(Share.item_id).where(Share.target_user_id == user_id)
        distance = FileEmbedding.embedding.cosine_distance(query).label("distance")
        # Per item, keep only its closest chunk (DISTINCT ON), then rank items.
        best = (
            select(
                FileEmbedding.item_id.label("item_id"),
                FileEmbedding.snippet.label("snippet"),
                distance,
            )
            .join(DriveItem, DriveItem.id == FileEmbedding.item_id)
            .where(
                DriveItem.is_deleted.is_(False),
                or_(DriveItem.owner_id == user_id, DriveItem.id.in_(shared_subq)),
            )
            .order_by(FileEmbedding.item_id, distance)
            .distinct(FileEmbedding.item_id)
            .subquery()
        )
        stmt = (
            select(DriveItem, best.c.snippet, best.c.distance)
            .join(best, best.c.item_id == DriveItem.id)
            .order_by(best.c.distance)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [(row[0], float(row[2]), row[1] or "") for row in result.all()]


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
        return [
            SemanticHit(item=item, score=1.0 - distance, snippet=snippet)
            for item, distance, snippet in rows
        ]


async def embed_chunks(client: EmbeddingClient, text: str) -> list[ChunkEmbedding]:
    """Chunk text and embed each chunk. Raises EmbeddingError if the service is down."""
    chunks: list[ChunkEmbedding] = []
    for index, piece in enumerate(chunk_text(text)):
        vector = await client.embed(piece)
        chunks.append(ChunkEmbedding(index=index, snippet=snippet_of(piece), vector=vector))
    return chunks


__all__ = [
    "AbstractFileEmbeddingRepository",
    "ChunkEmbedding",
    "SQLFileEmbeddingRepository",
    "SemanticHit",
    "SemanticSearchService",
    "chunk_text",
    "embed_chunks",
    "snippet_of",
]
