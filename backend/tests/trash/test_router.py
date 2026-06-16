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
from app.core.exceptions import AppError, NotFoundError
from app.core.security import create_access_token
from app.schemas.common import DriveItemResponse, Page
from app.trash.router import _trash_service
from app.trash.router import router as trash_router
from app.trash.service import TrashService

pytestmark = pytest.mark.asyncio

# ── helpers ──────────────────────────────────────────────────────────────────


def _item(owner_id: UUID, *, is_deleted: bool = False, name: str = "file.txt") -> DriveItemResponse:
    now = datetime.now(UTC)
    return DriveItemResponse(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=None,
        item_type="FILE",
        name=name,
        mime_type="text/plain",
        extension="txt",
        size_bytes=100,
        is_starred=False,
        is_deleted=is_deleted,
        deleted_at=now if is_deleted else None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def _make_app(service: TrashService, user_id: UUID) -> FastAPI:
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
    app.dependency_overrides[_trash_service] = lambda: service
    app.include_router(trash_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ── POST /trash/items/{item_id} ───────────────────────────────────────────────


async def test_move_to_trash_returns_200(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    trashed = _item(user_id, is_deleted=True)
    svc = AsyncMock(spec=TrashService)
    svc.trash_item.return_value = trashed
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{item_id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_deleted"] is True


async def test_move_to_trash_requires_auth() -> None:
    svc = AsyncMock(spec=TrashService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{uuid4()}")
    assert resp.status_code in (401, 403)


async def test_move_to_trash_item_not_found_returns_404(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=TrashService)
    svc.trash_item.side_effect = NotFoundError("Item not found")
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{uuid4()}", headers=headers)
    assert resp.status_code == 404


# ── GET /trash ────────────────────────────────────────────────────────────────


async def test_list_trash_returns_page(user_id: UUID, headers: dict[str, str]) -> None:
    items = [_item(user_id, is_deleted=True, name=f"del{i}.txt") for i in range(3)]
    page: Page[DriveItemResponse] = Page[DriveItemResponse].create(
        items, total=3, page=1, page_size=50
    )
    svc = AsyncMock(spec=TrashService)
    svc.list_trash.return_value = page
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/trash", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


async def test_list_trash_requires_auth() -> None:
    svc = AsyncMock(spec=TrashService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/trash")
    assert resp.status_code in (401, 403)


# ── POST /trash/items/{item_id}/restore ──────────────────────────────────────


async def test_restore_returns_200(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    restored = _item(user_id, is_deleted=False)
    svc = AsyncMock(spec=TrashService)
    svc.restore.return_value = restored
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{item_id}/restore", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_deleted"] is False


async def test_restore_requires_auth() -> None:
    svc = AsyncMock(spec=TrashService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{uuid4()}/restore")
    assert resp.status_code in (401, 403)


async def test_restore_item_not_found_returns_404(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=TrashService)
    svc.restore.side_effect = NotFoundError("Item not found")
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/trash/items/{uuid4()}/restore", headers=headers)
    assert resp.status_code == 404


# ── DELETE /trash/items/{item_id} ────────────────────────────────────────────


async def test_permanent_delete_returns_204(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    svc = AsyncMock(spec=TrashService)
    svc.permanent_delete.return_value = None
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/trash/items/{item_id}", headers=headers)
    assert resp.status_code == 204


async def test_permanent_delete_requires_auth() -> None:
    svc = AsyncMock(spec=TrashService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/trash/items/{uuid4()}")
    assert resp.status_code in (401, 403)


async def test_permanent_delete_not_found_returns_404(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=TrashService)
    svc.permanent_delete.side_effect = NotFoundError("Item not found")
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/trash/items/{uuid4()}", headers=headers)
    assert resp.status_code == 404


# ── DELETE /trash ─────────────────────────────────────────────────────────────


async def test_empty_trash_returns_204(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=TrashService)
    svc.empty_trash.return_value = None
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/trash", headers=headers)
    assert resp.status_code == 204


async def test_empty_trash_requires_auth() -> None:
    svc = AsyncMock(spec=TrashService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete("/trash")
    assert resp.status_code in (401, 403)
