from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from app.models.drive_item import DriveItem
from app.search.backfill import (
    AbstractEmbeddingBackfillRepository,
    EmbeddingBackfillService,
)
from app.search.embedding import EmbeddingClient, EmbeddingError
from app.search.semantic import AbstractFileEmbeddingRepository


class _FakeEmbed(EmbeddingClient):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def embed(self, text: str) -> list[float]:
        self.calls += 1
        if self.fail:
            raise EmbeddingError("down")
        return [0.1, 0.2]


class _MemBackfillRepo(AbstractEmbeddingBackfillRepository):
    def __init__(self, pending: dict[UUID, str]) -> None:
        self.pending = pending  # item_id -> content

    async def list_pending(self, *, user_id: UUID, limit: int) -> list[tuple[UUID, str]]:
        return list(self.pending.items())[:limit]

    async def count_pending(self, *, user_id: UUID) -> int:
        return len(self.pending)


class _MemEmbeddingRepo(AbstractFileEmbeddingRepository):
    def __init__(self, backfill: _MemBackfillRepo) -> None:
        self.backfill = backfill
        self.vectors: dict[UUID, list[float]] = {}

    async def upsert(
        self, *, item_id: UUID, embedding: list[float], model: str, updated_at: datetime
    ) -> None:
        self.vectors[item_id] = embedding
        # Once embedded, it's no longer pending — mirror real behaviour.
        self.backfill.pending.pop(item_id, None)

    async def delete(self, item_id: UUID) -> None:
        self.vectors.pop(item_id, None)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float]]:
        return []


def _service(
    pending: dict[UUID, str], *, fail: bool = False
) -> tuple[EmbeddingBackfillService, _MemEmbeddingRepo]:
    backfill_repo = _MemBackfillRepo(pending)
    embedding_repo = _MemEmbeddingRepo(backfill_repo)
    svc = EmbeddingBackfillService(
        embedding_client=_FakeEmbed(fail=fail),
        backfill_repo=backfill_repo,
        embedding_repo=embedding_repo,
        model="m",
    )
    return svc, embedding_repo


async def test_backfill_embeds_pending_and_reports_remaining() -> None:
    a, b, c = uuid4(), uuid4(), uuid4()
    svc, emb = _service({a: "alpha", b: "beta", c: "gamma"})

    result = await svc.run(user_id=uuid4(), batch_size=2)

    assert result.indexed == 2  # processed one batch
    assert result.remaining == 1  # one still pending
    assert len(emb.vectors) == 2


async def test_backfill_run_until_empty() -> None:
    items = {uuid4(): f"doc-{i}" for i in range(3)}
    svc, emb = _service(items)

    first = await svc.run(user_id=uuid4(), batch_size=10)

    assert first.indexed == 3
    assert first.remaining == 0
    assert len(emb.vectors) == 3


async def test_backfill_raises_when_embedding_service_down() -> None:
    svc, emb = _service({uuid4(): "x"}, fail=True)

    with pytest.raises(EmbeddingError):
        await svc.run(user_id=uuid4())

    assert emb.vectors == {}  # nothing written
