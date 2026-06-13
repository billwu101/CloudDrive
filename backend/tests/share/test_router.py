from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.core.security import create_access_token
from app.models.share_link import ShareLink
from app.permission.permissions import Permission
from app.schemas.common import Page
from app.share.router import _link_service, _share_service
from app.share.router import router as share_router
from app.share.schemas import ShareLinkResponse, ShareResponse
from app.share.service import ShareLinkService, ShareService

pytestmark = pytest.mark.asyncio

# ── helpers ──────────────────────────────────────────────────────────────────


def _share_resp(item_id: UUID, owner_id: UUID, target_id: UUID) -> ShareResponse:
    now = datetime.now(UTC)
    return ShareResponse(
        id=uuid4(),
        item_id=item_id,
        owner_id=owner_id,
        target_user_id=target_id,
        permission=Permission.VIEWER,
        created_at=now,
        updated_at=now,
    )


def _link_resp(item_id: UUID, created_by: UUID, token: str = "tok-abc") -> ShareLinkResponse:
    now = datetime.now(UTC)
    return ShareLinkResponse(
        id=uuid4(),
        item_id=item_id,
        token=token,
        permission=Permission.VIEWER,
        expires_at=None,
        is_active=True,
        created_by=created_by,
        created_at=now,
    )


def _make_app(share_svc: ShareService, link_svc: ShareLinkService, user_id: UUID) -> FastAPI:
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
    app.dependency_overrides[_share_service] = lambda: share_svc
    app.dependency_overrides[_link_service] = lambda: link_svc
    app.include_router(share_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


# ── POST /share/items/{item_id} ───────────────────────────────────────────────


async def test_share_item_returns_201(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    target_id = uuid4()
    share = _share_resp(item_id, user_id, target_id)
    share_svc = AsyncMock(spec=ShareService)
    share_svc.share_item.return_value = share
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{item_id}",
            json={"target_email": "bob@example.com", "permission": "viewer"},
            headers=headers,
        )
    assert resp.status_code == 201
    assert resp.json()["permission"] == "viewer"


async def test_share_item_requires_auth() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{uuid4()}",
            json={"target_email": "bob@example.com", "permission": "viewer"},
        )
    assert resp.status_code in (401, 403)


async def test_share_item_non_owner_returns_403(user_id: UUID, headers: dict[str, str]) -> None:
    share_svc = AsyncMock(spec=ShareService)
    share_svc.share_item.side_effect = ForbiddenError("Only the owner can share this item")
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{uuid4()}",
            json={"target_email": "bob@example.com", "permission": "viewer"},
            headers=headers,
        )
    assert resp.status_code == 403


async def test_share_item_target_not_found_returns_404(
    user_id: UUID, headers: dict[str, str]
) -> None:
    share_svc = AsyncMock(spec=ShareService)
    share_svc.share_item.side_effect = NotFoundError("User not found")
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{uuid4()}",
            json={"target_email": "notfound@example.com", "permission": "viewer"},
            headers=headers,
        )
    assert resp.status_code == 404


# ── DELETE /share/items/{item_id}/users/{target_user_id} ─────────────────────


async def test_remove_share_returns_204(user_id: UUID, headers: dict[str, str]) -> None:
    share_svc = AsyncMock(spec=ShareService)
    share_svc.remove_share.return_value = None
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(
            f"/share/items/{uuid4()}/users/{uuid4()}", headers=headers
        )
    assert resp.status_code == 204


async def test_remove_share_requires_auth() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/share/items/{uuid4()}/users/{uuid4()}")
    assert resp.status_code in (401, 403)


# ── GET /share/shared-with-me ────────────────────────────────────────────────


async def test_shared_with_me_returns_page(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    shares = [_share_resp(item_id, uuid4(), user_id)]
    page: Page[ShareResponse] = Page[ShareResponse].create(shares, total=1, page=1, page_size=20)
    share_svc = AsyncMock(spec=ShareService)
    share_svc.list_shared_with_me.return_value = page
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/share/shared-with-me", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["target_user_id"] == str(user_id)


async def test_shared_with_me_requires_auth() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/share/shared-with-me")
    assert resp.status_code in (401, 403)


# ── POST /share/items/{item_id}/links ─────────────────────────────────────────


async def test_create_link_returns_201(user_id: UUID, headers: dict[str, str]) -> None:
    item_id = uuid4()
    link = _link_resp(item_id, user_id)
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.create_link.return_value = link
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{item_id}/links",
            json={"permission": "viewer"},
            headers=headers,
        )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_active"] is True
    assert body["token"] == "tok-abc"


async def test_create_link_requires_auth() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{uuid4()}/links", json={"permission": "viewer"}
        )
    assert resp.status_code in (401, 403)


async def test_create_link_non_owner_returns_403(user_id: UUID, headers: dict[str, str]) -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.create_link.side_effect = ForbiddenError("Only the owner can create share links")
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            f"/share/items/{uuid4()}/links",
            json={"permission": "viewer"},
            headers=headers,
        )
    assert resp.status_code == 403


# ── POST /share/links/validate ────────────────────────────────────────────────


async def test_validate_link_returns_200(user_id: UUID) -> None:
    item_id = uuid4()
    raw_link = MagicMock(spec=ShareLink)
    raw_link.id = uuid4()
    raw_link.item_id = item_id
    raw_link.permission = Permission.VIEWER
    raw_link.expires_at = None
    raw_link.is_active = True
    raw_link.created_by = user_id
    raw_link.created_at = datetime.now(UTC)
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.validate_access.return_value = raw_link
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/share/links/validate", params={"token": "public-tok-abc"})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


async def test_validate_link_invalid_token_returns_404() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.validate_access.side_effect = NotFoundError("Link not found or inactive")
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/share/links/validate", params={"token": "bad-token"})
    assert resp.status_code == 404


# ── DELETE /share/links/{link_id} ────────────────────────────────────────────


async def test_deactivate_link_returns_204(user_id: UUID, headers: dict[str, str]) -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.deactivate_link.return_value = None
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/share/links/{uuid4()}", headers=headers)
    assert resp.status_code == 204


async def test_deactivate_link_requires_auth() -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    app = _make_app(share_svc, link_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/share/links/{uuid4()}")
    assert resp.status_code in (401, 403)


async def test_deactivate_link_non_owner_returns_403(
    user_id: UUID, headers: dict[str, str]
) -> None:
    share_svc = AsyncMock(spec=ShareService)
    link_svc = AsyncMock(spec=ShareLinkService)
    link_svc.deactivate_link.side_effect = ForbiddenError("Only the owner can deactivate this link")
    app = _make_app(share_svc, link_svc, user_id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"/share/links/{uuid4()}", headers=headers)
    assert resp.status_code == 403
