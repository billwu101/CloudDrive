"""Router tests for the guest share endpoints.

The point of these is the wiring the service tests cannot see: that the routes
work with no user session at all, and that the credential is read from the
Authorization header rather than a user token.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.drive.schemas import ItemType
from app.preview.service import PreviewType
from app.public_share.router import _public_share_service
from app.public_share.router import router as public_router
from app.public_share.schemas import PublicItemResponse, PublicSessionResponse
from app.public_share.service import PublicShareService

pytestmark = pytest.mark.asyncio


async def _fake_db() -> AsyncGenerator[Any, None]:
    yield AsyncMock()


def _make_app(service: PublicShareService) -> FastAPI:
    app = FastAPI()

    async def _handler(_request: Any, exc: Exception) -> JSONResponse:
        assert isinstance(exc, AppError)
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": {}}},
        )

    app.add_exception_handler(AppError, _handler)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_public_share_service] = lambda: service
    app.include_router(public_router)
    return app


def _item() -> PublicItemResponse:
    return PublicItemResponse(
        id=uuid4(),
        name="report.txt",
        item_type=ItemType.FILE,
        mime_type="text/plain",
        size_bytes=5,
        extension="txt",
        preview_type=PreviewType.TEXT,
        updated_at=datetime.now(UTC),
    )


def _session() -> PublicSessionResponse:
    return PublicSessionResponse(
        access_token="share-cred", expires_in=900, permission="downloader", item=_item()
    )


async def test_open_session_needs_no_authentication() -> None:
    """The whole feature exists for people who have no account."""
    svc = AsyncMock(spec=PublicShareService)
    svc.open_session.return_value = _session()
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/public/links/tok-abc/session", json={})
    assert resp.status_code == 200
    assert resp.json()["access_token"] == "share-cred"


async def test_password_travels_in_the_body_not_the_query_string() -> None:
    svc = AsyncMock(spec=PublicShareService)
    svc.open_session.return_value = _session()
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/public/links/tok-abc/session", json={"password": "s3cret"})
    assert resp.status_code == 200
    svc.open_session.assert_awaited_once_with("tok-abc", "s3cret")
    # Nothing secret may end up somewhere that gets logged.
    assert "s3cret" not in str(resp.request.url)


async def test_content_routes_require_a_credential() -> None:
    svc = AsyncMock(spec=PublicShareService)
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/public/items")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == ErrorCode.SHARE_LINK_INVALID


async def test_credential_is_forwarded_from_the_authorization_header() -> None:
    svc = AsyncMock(spec=PublicShareService)
    svc.get_root.return_value = _item()
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/public/items", headers={"Authorization": "Bearer share-cred"})
    assert resp.status_code == 200
    svc.get_root.assert_awaited_once_with("share-cred")


async def test_a_user_access_token_is_just_passed_through_and_rejected() -> None:
    """A logged-in user's token buys nothing here — the service still decides."""
    svc = AsyncMock(spec=PublicShareService)
    svc.get_root.side_effect = AppError(
        ErrorCode.SHARE_LINK_INVALID, "Link is invalid or no longer available", status_code=404
    )
    app = _make_app(svc)
    user_token = create_access_token(uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/public/items", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 404


async def test_invalid_link_returns_the_generic_error() -> None:
    svc = AsyncMock(spec=PublicShareService)
    svc.open_session.side_effect = AppError(
        ErrorCode.SHARE_LINK_INVALID, "Link is invalid or no longer available", status_code=404
    )
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/public/links/nope/session", json={})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == ErrorCode.SHARE_LINK_INVALID


async def test_selected_archive_passes_the_ids_through_and_needs_a_credential() -> None:
    """proposal §34.4 — the ids travel in the body, not the URL."""
    ids = [uuid4(), uuid4()]

    async def _chunks() -> AsyncGenerator[bytes, None]:
        yield b"zip"

    svc = AsyncMock(spec=PublicShareService)
    svc.archive.return_value = SimpleNamespace(
        stream=_chunks(), filename="Shared.zip", size_bytes=None
    )
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/public/archive",
            json={"item_ids": [str(i) for i in ids]},
            headers={"Authorization": "Bearer share-cred"},
        )

    assert resp.status_code == 200
    svc.archive.assert_awaited_once_with("share-cred", ids)
    # A selection can be long; keeping it out of the URL also keeps it out of logs.
    assert str(ids[0]) not in str(resp.request.url)


async def test_selected_archive_without_a_credential_is_refused() -> None:
    svc = AsyncMock(spec=PublicShareService)
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/public/archive", json={"item_ids": [str(uuid4())]})
    assert resp.status_code == 401
    svc.archive.assert_not_awaited()
