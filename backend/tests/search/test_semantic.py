from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.models.drive_item import DriveItem
from app.search.embedding import EmbeddingClient
from app.search.semantic import (
    AbstractFileEmbeddingRepository,
    ChunkEmbedding,
    SemanticSearchService,
    chunk_text,
)
from tests.snapshot.test_service import _item


class _FakeEmbed(EmbeddingClient):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0, 0.0]


class _MemEmbeddingRepo(AbstractFileEmbeddingRepository):
    def __init__(self, results: list[tuple[DriveItem, float, str]] | None = None) -> None:
        self.results = results or []
        self.chunks: dict[UUID, list[ChunkEmbedding]] = {}
        self.deleted: list[UUID] = []

    async def replace_chunks(
        self, *, item_id: UUID, chunks: list[ChunkEmbedding], model: str, updated_at: datetime
    ) -> None:
        self.chunks[item_id] = chunks

    async def delete(self, item_id: UUID) -> None:
        self.deleted.append(item_id)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float, str]]:
        return self.results[:limit]


async def test_search_maps_distance_to_similarity_and_returns_snippet() -> None:
    item = _item(uuid4(), name="quarterly.txt")
    repo = _MemEmbeddingRepo([(item, 0.2, "the snippet text")])
    svc = SemanticSearchService(embedding_client=_FakeEmbed(), repo=repo)

    hits = await svc.search(user_id=uuid4(), query="revenue")

    assert len(hits) == 1
    assert hits[0].item is item
    assert abs(hits[0].score - 0.8) < 1e-9  # score = 1 - cosine distance
    assert hits[0].snippet == "the snippet text"


async def test_blank_query_returns_empty_without_embedding() -> None:
    embed = _FakeEmbed()
    svc = SemanticSearchService(embedding_client=embed, repo=_MemEmbeddingRepo())

    assert await svc.search(user_id=uuid4(), query="   ") == []
    assert embed.calls == []  # never hit the embedding service


def test_chunk_text_short_text_is_single_chunk() -> None:
    assert chunk_text("hello world") == ["hello world"]


def test_chunk_text_splits_long_text_with_overlap() -> None:
    text = "x" * 2500
    chunks = chunk_text(text, size=1000, overlap=100)
    assert len(chunks) == 3  # 0-1000, 900-1900, 1800-2500
    assert all(len(c) <= 1000 for c in chunks)
    assert chunks[1][:100] == text[900:1000]  # overlap carried over


def test_chunk_text_blank_returns_empty() -> None:
    assert chunk_text("   ") == []
