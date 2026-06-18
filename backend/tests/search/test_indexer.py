from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.models.drive_item import DriveItem
from app.search.embedding import EmbeddingClient, EmbeddingError
from app.search.indexer import AbstractSearchIndexRepository, SearchIndexService
from app.search.semantic import AbstractFileEmbeddingRepository


class MemSearchIndexRepo(AbstractSearchIndexRepository):
    def __init__(self) -> None:
        self.content: dict[UUID, str] = {}

    async def upsert(self, *, item_id: UUID, content: str, updated_at: datetime) -> None:
        self.content[item_id] = content

    async def delete(self, item_id: UUID) -> None:
        self.content.pop(item_id, None)


class _MemEmbeddingRepo(AbstractFileEmbeddingRepository):
    def __init__(self) -> None:
        self.vectors: dict[UUID, list[float]] = {}
        self.deleted: list[UUID] = []

    async def upsert(
        self, *, item_id: UUID, embedding: list[float], model: str, updated_at: datetime
    ) -> None:
        self.vectors[item_id] = embedding

    async def delete(self, item_id: UUID) -> None:
        self.vectors.pop(item_id, None)
        self.deleted.append(item_id)

    async def semantic_search(
        self, *, user_id: UUID, query: list[float], limit: int
    ) -> list[tuple[DriveItem, float]]:
        return []


class _FakeEmbed(EmbeddingClient):
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    async def embed(self, text: str) -> list[float]:
        if self.fail:
            raise EmbeddingError("down")
        return [0.5, 0.5]


async def test_index_file_stores_extracted_text() -> None:
    repo = MemSearchIndexRepo()
    svc = SearchIndexService(repo)
    item_id = uuid4()

    indexed = await svc.index_file(
        item_id=item_id, data=b"quarterly revenue report", mime_type="text/plain", extension="txt"
    )

    assert indexed is True
    assert repo.content[item_id] == "quarterly revenue report"


async def test_index_file_unsupported_type_skips_and_clears_stale() -> None:
    repo = MemSearchIndexRepo()
    svc = SearchIndexService(repo)
    item_id = uuid4()
    repo.content[item_id] = "stale text from a previous version"

    indexed = await svc.index_file(
        item_id=item_id, data=b"\x00\x01\x02", mime_type="image/png", extension="png"
    )

    assert indexed is False
    assert item_id not in repo.content  # stale index removed


async def test_index_file_also_writes_embedding_when_enabled() -> None:
    repo = MemSearchIndexRepo()
    emb_repo = _MemEmbeddingRepo()
    svc = SearchIndexService(
        repo, embedding_client=_FakeEmbed(), embedding_repo=emb_repo, embedding_model="m"
    )
    item_id = uuid4()

    await svc.index_file(
        item_id=item_id, data=b"hello text", mime_type="text/plain", extension="txt"
    )

    assert repo.content[item_id] == "hello text"
    assert emb_repo.vectors[item_id] == [0.5, 0.5]


async def test_embedding_failure_does_not_break_full_text_index() -> None:
    repo = MemSearchIndexRepo()
    emb_repo = _MemEmbeddingRepo()
    svc = SearchIndexService(
        repo,
        embedding_client=_FakeEmbed(fail=True),
        embedding_repo=emb_repo,
        embedding_model="m",
    )
    item_id = uuid4()

    indexed = await svc.index_file(
        item_id=item_id, data=b"hello text", mime_type="text/plain", extension="txt"
    )

    assert indexed is True
    assert repo.content[item_id] == "hello text"  # full-text still written
    assert item_id not in emb_repo.vectors  # embedding skipped, no crash


async def test_unsupported_type_clears_embedding_too() -> None:
    repo = MemSearchIndexRepo()
    emb_repo = _MemEmbeddingRepo()
    emb_repo.vectors[(item_id := uuid4())] = [1.0]
    svc = SearchIndexService(
        repo, embedding_client=_FakeEmbed(), embedding_repo=emb_repo, embedding_model="m"
    )

    indexed = await svc.index_file(
        item_id=item_id, data=b"\x00\x01", mime_type="image/png", extension="png"
    )

    assert indexed is False
    assert item_id in emb_repo.deleted
