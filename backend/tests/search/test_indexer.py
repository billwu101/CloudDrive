from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from app.search.indexer import AbstractSearchIndexRepository, SearchIndexService


class MemSearchIndexRepo(AbstractSearchIndexRepository):
    def __init__(self) -> None:
        self.content: dict[UUID, str] = {}

    async def upsert(self, *, item_id: UUID, content: str, updated_at: datetime) -> None:
        self.content[item_id] = content

    async def delete(self, item_id: UUID) -> None:
        self.content.pop(item_id, None)


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
