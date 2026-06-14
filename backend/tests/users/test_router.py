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
from app.core.error_codes import ErrorCode
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


async def test_update_me_rejects_blank_username() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch("/users/me", json={"username": "   "}, headers=_headers(uid))
    assert resp.status_code == 422
    svc.update_username.assert_not_awaited()


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


async def test_update_email() -> None:
    uid = uuid4()
    user = _user(uid)
    user.email = "new@example.com"
    svc = AsyncMock(spec=UserService)
    svc.update_email.return_value = user
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/email",
            json={"email": "new@example.com"},
            headers=_headers(uid),
        )
    assert resp.status_code == 200
    assert resp.json()["email"] == "new@example.com"
    svc.update_email.assert_awaited_once_with(uid, "new@example.com")


async def test_update_email_normalizes_value() -> None:
    uid = uuid4()
    user = _user(uid)
    user.email = "new@example.com"
    svc = AsyncMock(spec=UserService)
    svc.update_email.return_value = user
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/email",
            json={"email": "  New@Example.COM  "},
            headers=_headers(uid),
        )
    assert resp.status_code == 200
    svc.update_email.assert_awaited_once_with(uid, "new@example.com")


async def test_update_email_rejects_invalid_address() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/email",
            json={"email": "not-an-email"},
            headers=_headers(uid),
        )
    assert resp.status_code == 422
    svc.update_email.assert_not_awaited()


async def test_update_email_conflict_returns_409() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    svc.update_email.side_effect = AppError(
        ErrorCode.EMAIL_ALREADY_EXISTS, "Email already in use", status_code=409
    )
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/email",
            json={"email": "taken@example.com"},
            headers=_headers(uid),
        )
    assert resp.status_code == 409


async def test_update_email_requires_auth() -> None:
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch("/users/me/email", json={"email": "x@example.com"})
    assert resp.status_code in (401, 403)


async def test_change_password() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    svc.change_password.return_value = None
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/password",
            json={"current_password": "old_pass", "new_password": "new_secure_pass"},
            headers=_headers(uid),
        )
    assert resp.status_code == 204


async def test_change_password_wrong_current_returns_400() -> None:
    uid = uuid4()
    svc = AsyncMock(spec=UserService)
    svc.change_password.side_effect = AppError(
        ErrorCode.INVALID_CREDENTIALS, "Current password is incorrect", status_code=400
    )
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uid)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/password",
            json={"current_password": "wrong", "new_password": "new_secure_pass"},
            headers=_headers(uid),
        )
    assert resp.status_code == 400


async def test_change_password_requires_auth() -> None:
    svc = AsyncMock(spec=UserService)
    quota_svc = AsyncMock(spec=QuotaService)
    app = _make_app(svc, quota_svc, uuid4())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.patch(
            "/users/me/password",
            json={"current_password": "x", "new_password": "newpassword123"},
        )
    assert resp.status_code in (401, 403)
