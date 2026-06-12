from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.models.user import User
from app.users.router import _quota_service, _user_service
from app.users.router import router as users_router
from app.users.schemas import QuotaResponse
from app.users.service import QuotaService, UserService


def _user(user_id: UUID) -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id,
        email="test@example.com",
        username="testuser",
        password_hash="hash",
        avatar_url=None,
        quota_bytes=10 * 1024 * 1024,
        used_bytes=1024,
        is_active=True,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _make_app(
    user_svc: UserService,
    quota_svc: QuotaService,
    user_id: UUID,
) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": str(exc.code), "message": exc.message}},
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_user_service] = lambda: user_svc
    app.dependency_overrides[_quota_service] = lambda: quota_svc
    app.include_router(users_router)
    return app


def _headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def test_get_me() -> None:
    uid = uuid4()
    user = _user(uid)
    svc = AsyncMock(spec=UserService)
    svc.get_by_id.return_value = user
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/users/me", headers=_headers(uid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "test@example.com"
    assert body["username"] == "testuser"


async def test_update_me() -> None:
    uid = uuid4()
    user = _user(uid)
    user.username = "updated"
    svc = AsyncMock(spec=UserService)
    svc.update_username.return_value = user
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch("/users/me", json={"username": "updated"}, headers=_headers(uid))
    assert resp.status_code == 200
    assert resp.json()["username"] == "updated"


async def test_get_my_quota() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    quota_svc.get_quota_info.return_value = QuotaResponse(
        quota_bytes=10 * 1024 * 1024,
        used_bytes=1024,
        available_bytes=10 * 1024 * 1024 - 1024,
        used_percent=0.01,
    )
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/users/me/quota", headers=_headers(uid))
    assert resp.status_code == 200
    body = resp.json()
    assert body["quota_bytes"] == 10 * 1024 * 1024
    assert body["available_bytes"] == 10 * 1024 * 1024 - 1024


async def test_get_me_requires_auth() -> None:
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/users/me")
    assert resp.status_code in (401, 403)
