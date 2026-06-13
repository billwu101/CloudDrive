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
from app.drive.router import _drive_service
from app.drive.router import router as drive_router
from app.drive.schemas import ItemType
from app.drive.service import DriveService
from app.schemas.common import DriveItemResponse, Page

# ── helpers ──────────────────────────────────────────────────────────────────


def _resp(
    *,
    owner_id: UUID,
    parent_id: UUID | None = None,
    name: str = "Folder",
    item_type: str = ItemType.FOLDER,
) -> DriveItemResponse:
    now = datetime.now(UTC)
    uid = uuid4()
    return DriveItemResponse(
        id=uid,
        owner_id=owner_id,
        parent_id=parent_id,
        item_type=item_type,
        name=name,
        mime_type=None,
        extension=None,
        size_bytes=0,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def _make_app(service: DriveService, user_id: UUID) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": str(exc.code), "message": exc.message, "details": exc.details}
            },
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_drive_service] = lambda: service
    app.include_router(drive_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def access_token(user_id: UUID) -> str:
    return create_access_token(user_id)


@pytest.fixture()
def headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# ── GET /drive/items ─────────────────────────────────────────────────────────


async def test_list_items_returns_page(user_id: UUID, headers: dict[str, str]) -> None:
    page: Page[DriveItemResponse] = Page[DriveItemResponse].create(
        [_resp(owner_id=user_id)], total=1, page=1, page_size=20
    )
    svc = AsyncMock(spec=DriveService)
    svc.list_items.return_value = page
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/drive/items", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


async def test_list_items_requires_auth() -> None:
    svc = AsyncMock(spec=DriveService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/drive/items")
    assert resp.status_code in (401, 403)


# ── POST /drive/folders ───────────────────────────────────────────────────────


async def test_create_folder_success(user_id: UUID, headers: dict[str, str]) -> None:
    folder = _resp(owner_id=user_id, name="NewFolder")
    svc = AsyncMock(spec=DriveService)
    svc.create_folder.return_value = folder
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/drive/folders", json={"name": "NewFolder"}, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["name"] == "NewFolder"


async def test_create_folder_missing_name_returns_422(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=DriveService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/drive/folders", json={}, headers=headers)
    assert resp.status_code == 422


# ── PATCH /drive/items/{id}/name ─────────────────────────────────────────────


async def test_rename_item(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    renamed = _resp(owner_id=user_id, name="renamed")
    svc = AsyncMock(spec=DriveService)
    svc.rename.return_value = renamed
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/drive/items/{item_id}/name", json={"name": "renamed"}, headers=headers
        )
    assert resp.status_code == 200
    assert resp.json()["name"] == "renamed"


# ── PATCH /drive/items/{id}/parent ───────────────────────────────────────────


async def test_move_item(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    new_parent = uuid4()
    moved = _resp(owner_id=user_id, parent_id=new_parent)
    svc = AsyncMock(spec=DriveService)
    svc.move.return_value = moved
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            f"/drive/items/{item_id}/parent",
            json={"parent_id": str(new_parent)},
            headers=headers,
        )
    assert resp.status_code == 200


# ── PUT /drive/items/{id}/star ────────────────────────────────────────────────


async def test_star_item(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    starred = _resp(owner_id=user_id)
    starred_copy = DriveItemResponse(**{**starred.model_dump(), "is_starred": True})
    svc = AsyncMock(spec=DriveService)
    svc.set_starred.return_value = starred_copy
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            f"/drive/items/{item_id}/star", json={"is_starred": True}, headers=headers
        )
    assert resp.status_code == 200
    assert resp.json()["is_starred"] is True


# ── GET /drive/recent ─────────────────────────────────────────────────────────


async def test_get_recent(user_id: UUID, headers: dict[str, str]) -> None:
    recent_items = [_resp(owner_id=user_id, name=f"item{i}") for i in range(3)]
    svc = AsyncMock(spec=DriveService)
    svc.get_recent.return_value = recent_items
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/drive/recent", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ── GET /drive/items/{id}/ancestors ──────────────────────────────────────────


async def test_get_ancestors_returns_list(user_id: UUID, headers: dict[str, str]) -> None:
    ancestors = [_resp(owner_id=user_id, name="Root"), _resp(owner_id=user_id, name="Sub")]
    svc = AsyncMock(spec=DriveService)
    svc.get_ancestors.return_value = ancestors
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/drive/items/{uuid4()}/ancestors", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["name"] == "Root"
    assert body[1]["name"] == "Sub"


async def test_get_ancestors_requires_auth() -> None:
    svc = AsyncMock(spec=DriveService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/drive/items/{uuid4()}/ancestors")
    assert resp.status_code in (401, 403)


async def test_get_ancestors_root_item_returns_empty(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=DriveService)
    svc.get_ancestors.return_value = []
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/drive/items/{uuid4()}/ancestors", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []
