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
from app.core.exceptions import AppError, NotFoundError, QuotaExceededError
from app.core.security import create_access_token
from app.schemas.common import DriveItemResponse
from app.upload.router import _upload_service
from app.upload.router import router as upload_router
from app.upload.service import UploadService

pytestmark = pytest.mark.asyncio

# ── helpers ──────────────────────────────────────────────────────────────────


def _item_resp(owner_id: UUID, name: str = "hello.txt") -> DriveItemResponse:
    now = datetime.now(UTC)
    return DriveItemResponse(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=None,
        item_type="FILE",
        name=name,
        mime_type="text/plain",
        extension="txt",
        size_bytes=13,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


def _make_app(service: UploadService, user_id: UUID) -> FastAPI:
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
    app.dependency_overrides[_upload_service] = lambda: service
    app.include_router(upload_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ── POST /upload/simple ───────────────────────────────────────────────────────


async def test_upload_simple_returns_201(user_id: UUID, headers: dict[str, str]) -> None:
    item = _item_resp(user_id)
    svc = AsyncMock(spec=UploadService)
    svc.upload_simple.return_value = item
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/upload/simple",
            headers=headers,
            files={"file": ("hello.txt", b"Hello, world!", "text/plain")},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["item_type"] == "FILE"
    assert body["name"] == "hello.txt"


async def test_upload_simple_requires_auth() -> None:
    svc = AsyncMock(spec=UploadService)
    app = _make_app(svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/upload/simple",
            files={"file": ("f.txt", b"data", "text/plain")},
        )
    assert resp.status_code in (401, 403)


async def test_upload_simple_parent_not_found_returns_404(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadService)
    svc.upload_simple.side_effect = NotFoundError("Parent folder not found")
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/upload/simple",
            headers=headers,
            files={"file": ("f.txt", b"data", "text/plain")},
            params={"parent_id": str(uuid4())},
        )
    assert resp.status_code == 404


async def test_upload_simple_quota_exceeded_returns_413(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadService)
    svc.upload_simple.side_effect = QuotaExceededError("Storage quota exceeded")
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/upload/simple",
            headers=headers,
            files={"file": ("big.bin", b"x" * 100, "application/octet-stream")},
        )
    assert resp.status_code == 413


async def test_upload_simple_passes_parent_id_to_service(
    user_id: UUID, headers: dict[str, str]
) -> None:
    parent_id = uuid4()
    item = _item_resp(user_id)
    svc = AsyncMock(spec=UploadService)
    svc.upload_simple.return_value = item
    app = _make_app(svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post(
            "/upload/simple",
            headers=headers,
            files={"file": ("f.txt", b"hi", "text/plain")},
            params={"parent_id": str(parent_id)},
        )
    call_kwargs = svc.upload_simple.call_args
    assert call_kwargs.kwargs.get("parent_id") == parent_id or (
        len(call_kwargs.args) > 1 and parent_id in call_kwargs.args
    )
