from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.schemas.common import DriveItemResponse, Page
from app.search.router import _search_service
from app.search.router import router as search_router
from app.search.service import SearchService

pytestmark = pytest.mark.asyncio

# ── helpers ──────────────────────────────────────────────────────────────────


def _item(owner_id: UUID, name: str = "report.pdf") -> DriveItemResponse:
    now = datetime.now(UTC)
    return DriveItemResponse(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=None,
        item_type="FILE",
        name=name,
        mime_type="application/pdf",
        extension="pdf",
        size_bytes=204800,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def _make_app(service: SearchService, user_id: UUID) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": str(exc.code), "message": exc.message},
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_search_service] = lambda: service
    app.include_router(search_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ── GET /search ───────────────────────────────────────────────────────────────


async def test_search_returns_page(user_id: UUID, headers: dict[str, str]) -> None:
    items = [_item(user_id, "quarterly_report.pdf")]
    page: Page[DriveItemResponse] = Page[DriveItemResponse].create(
        items, total=1, page=1, page_size=20
    )
    svc = AsyncMock(spec=SearchService)
    svc.search.return_value = page
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search", params={"q": "quarterly"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "quarterly_report.pdf"


async def test_search_empty_result(user_id: UUID, headers: dict[str, str]) -> None:
    page: Page[DriveItemResponse] = Page[DriveItemResponse].create(
        [], total=0, page=1, page_size=20
    )
    svc = AsyncMock(spec=SearchService)
    svc.search.return_value = page
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search", params={"q": "xyznonexistent"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


async def test_search_requires_auth() -> None:
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search", params={"q": "test"})
    assert resp.status_code in (401, 403)


async def test_search_missing_q_returns_422(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search", headers=headers)
    assert resp.status_code == 422


async def test_search_passes_filters_to_service(user_id: UUID, headers: dict[str, str]) -> None:
    page: Page[DriveItemResponse] = Page[DriveItemResponse].create(
        [], total=0, page=1, page_size=20
    )
    svc = AsyncMock(spec=SearchService)
    svc.search.return_value = page
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get(
            "/search",
            params={"q": "doc", "item_type": "file", "mime_type": "application/pdf", "page": 2},
            headers=headers,
        )
    call_kwargs = svc.search.call_args.kwargs
    assert call_kwargs.get("item_type") == "file"
    assert call_kwargs.get("mime_type") == "application/pdf"
    assert call_kwargs.get("page") == 2


# ── GET /search/semantic ───────────────────────────────────────────────────────


async def test_semantic_search_disabled_returns_503(user_id: UUID, headers: dict[str, str]) -> None:
    # Embeddings are disabled by default, so the factory yields no service.
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search/semantic", params={"q": "ideas"}, headers=headers)
    assert resp.status_code == 503


async def test_semantic_search_returns_hits(
    monkeypatch: pytest.MonkeyPatch, user_id: UUID, headers: dict[str, str]
) -> None:
    from app.search.semantic import SemanticHit

    hit_item = _item(user_id, name="thesis.pdf")

    class _FakeSemanticService:
        async def search(self, *, user_id: UUID, query: str, limit: int) -> list[SemanticHit]:
            # _to_response reads the same attributes off a DriveItemResponse.
            return [SemanticHit(item=hit_item, score=0.91)]  # type: ignore[arg-type]

    monkeypatch.setattr(
        "app.search.router.build_semantic_search_service",
        lambda session, settings: _FakeSemanticService(),
    )
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search/semantic", params={"q": "machine learning"}, headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["item"]["name"] == "thesis.pdf"
    assert abs(body[0]["score"] - 0.91) < 1e-6


async def test_semantic_search_embedding_down_returns_503(
    monkeypatch: pytest.MonkeyPatch, user_id: UUID, headers: dict[str, str]
) -> None:
    from app.search.embedding import EmbeddingError

    class _BoomService:
        async def search(self, *, user_id: UUID, query: str, limit: int) -> list[object]:
            raise EmbeddingError("down")

    monkeypatch.setattr(
        "app.search.router.build_semantic_search_service",
        lambda session, settings: _BoomService(),
    )
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/search/semantic", params={"q": "x"}, headers=headers)
    assert resp.status_code == 503


# ── POST /search/embeddings/backfill ────────────────────────────────────────────


async def test_backfill_disabled_returns_503(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/search/embeddings/backfill", headers=headers)
    assert resp.status_code == 503


async def test_backfill_returns_counts(
    monkeypatch: pytest.MonkeyPatch, user_id: UUID, headers: dict[str, str]
) -> None:
    from app.search.backfill import BackfillResult

    class _FakeBackfill:
        async def run(self, *, user_id: UUID, batch_size: int) -> BackfillResult:
            return BackfillResult(indexed=3, remaining=7)

    monkeypatch.setattr(
        "app.search.router.build_embedding_backfill_service",
        lambda session, settings: _FakeBackfill(),
    )
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/search/embeddings/backfill", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"indexed": 3, "remaining": 7}


async def test_backfill_embedding_down_returns_503(
    monkeypatch: pytest.MonkeyPatch, user_id: UUID, headers: dict[str, str]
) -> None:
    from app.search.embedding import EmbeddingError

    class _BoomBackfill:
        async def run(self, *, user_id: UUID, batch_size: int) -> object:
            raise EmbeddingError("down")

    monkeypatch.setattr(
        "app.search.router.build_embedding_backfill_service",
        lambda session, settings: _BoomBackfill(),
    )
    svc = AsyncMock(spec=SearchService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/search/embeddings/backfill", headers=headers)
    assert resp.status_code == 503
