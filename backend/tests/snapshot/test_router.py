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
from app.models.snapshot import Snapshot, SnapshotEntry
from app.snapshot.router import _snapshot_service
from app.snapshot.router import router as snapshot_router
from app.snapshot.service import RestoreOutcome, SnapshotService

pytestmark = pytest.mark.asyncio


def _snapshot(user: UUID) -> Snapshot:
    return Snapshot(
        id=uuid4(),
        user_id=user,
        trigger="manual",
        label="manual",
        item_count=3,
        total_bytes=350,
        pinned=False,
        created_at=datetime.now(UTC),
    )


def _entry(name: str, item_type: str = "FILE") -> SnapshotEntry:
    return SnapshotEntry(
        id=uuid4(),
        snapshot_id=uuid4(),
        item_id=uuid4(),
        parent_item_id=None,
        name=name,
        item_type=item_type,
        storage_key="k/x" if item_type == "FILE" else None,
        checksum_sha256="abc" if item_type == "FILE" else None,
        size_bytes=100 if item_type == "FILE" else 0,
    )


def _make_app(service: SnapshotService, user_id: UUID) -> FastAPI:
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
    app.dependency_overrides[_snapshot_service] = lambda: service
    app.include_router(snapshot_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def test_create_snapshot_returns_200(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SnapshotService)
    svc.create.return_value = _snapshot(user_id)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/snapshots", json={"label": "manual"}, headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["item_count"] == 3
    assert body["trigger"] == "manual"


async def test_list_snapshots(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SnapshotService)
    svc.list_snapshots.return_value = [_snapshot(user_id), _snapshot(user_id)]
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/snapshots", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_browse_snapshot_items(user_id: UUID, headers: dict[str, str]) -> None:
    sid = uuid4()
    svc = AsyncMock(spec=SnapshotService)
    svc.browse.return_value = [_entry("docs", "FOLDER"), _entry("root.txt")]
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/snapshots/{sid}/items", headers=headers)
    assert resp.status_code == 200
    assert {e["name"] for e in resp.json()} == {"docs", "root.txt"}


async def test_browse_unknown_snapshot_returns_404(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SnapshotService)
    svc.browse.return_value = None
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/snapshots/{uuid4()}/items", headers=headers)
    assert resp.status_code == 404


async def test_restore_returns_200(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SnapshotService)
    svc.restore.return_value = RestoreOutcome(
        pre_restore_snapshot_id=uuid4(), restored=5, trashed=2
    )
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/snapshots/{uuid4()}/restore",
            json={"scope": "whole", "subtree_mode": "exact_mirror"},
            headers=headers,
        )
    assert resp.status_code == 200
    assert resp.json()["restored"] == 5
    assert resp.json()["trashed"] == 2


async def test_restore_unknown_snapshot_returns_404(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=SnapshotService)
    svc.restore.return_value = None
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(f"/snapshots/{uuid4()}/restore", json={}, headers=headers)
    assert resp.status_code == 404


async def test_snapshots_require_auth(user_id: UUID) -> None:
    svc = AsyncMock(spec=SnapshotService)
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/snapshots")
    assert resp.status_code in (401, 403)
