from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.models.drive_item import DriveItem
from app.search.embedding import EmbeddingClient
from app.search.semantic import (
    AbstractFileEmbeddingRepository,
    SemanticSearchService,
    embeddable_text,
)
from tests.snapshot.test_service import _item


class _FakeEmbed(EmbeddingClient):
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        return [1.0, 0.0, 0.0]


class _MemEmbeddingRepo(AbstractFileEmbeddingRepository):
    def __init__(self, results: list[tuple[DriveItem, float]] | None = None) -> None:
        self.results = results or []
        self.upserts: dict[UUID, list[float]] = {}
        self.deleted: list[UUID] = []

    async def upsert(
        self, *, item_id: UUID, embedding: list[float], model: str, updated_at: datetime
    ) -> None:
        self.upserts[item_id] = embedding

    async def delete(self, item_id: UUID) -> None:
        self.deleted.append(item_id)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float]]:
        return self.results[:limit]


async def test_search_maps_distance_to_similarity_score() -> None:
    item = _item(uuid4(), name="quarterly.txt")
    svc = SemanticSearchService(
        embedding_client=_FakeEmbed(), repo=_MemEmbeddingRepo([(item, 0.2)])
    )

    hits = await svc.search(user_id=uuid4(), query="revenue")

    assert len(hits) == 1
    assert hits[0].item is item
    assert abs(hits[0].score - 0.8) < 1e-9  # score = 1 - cosine distance


async def test_blank_query_returns_empty_without_embedding() -> None:
    embed = _FakeEmbed()
    svc = SemanticSearchService(embedding_client=embed, repo=_MemEmbeddingRepo())

    assert await svc.search(user_id=uuid4(), query="   ") == []
    assert embed.calls == []  # never hit the embedding service


def test_embeddable_text_is_truncated() -> None:
    assert len(embeddable_text("x" * 10_000)) == 8_000
