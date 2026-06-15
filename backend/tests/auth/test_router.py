from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.auth.repository import (
    AbstractRefreshTokenRepository,
    AbstractUserRepository,
    hash_token,
)
from app.auth.router import _is_secure_cookie_environment
from app.auth.router import router as auth_router
from app.auth.service import AuthService
from app.core.dependencies import get_db
from app.core.security import create_access_token, hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User

# ── Minimal in-memory fakes ──────────────────────────────────────────────────


def _user(
    *,
    email: str = "test@example.com",
    password: str = "password123",
    is_active: bool = True,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=email,
        username="testuser",
        password_hash=hash_password(password),
        avatar_url=None,
        quota_bytes=15 * 1024**3,
        used_bytes=0,
        is_active=is_active,
        is_admin=False,
        must_change_password=False,
        created_at=now,
        updated_at=now,
    )


class FakeUserRepo(AbstractUserRepository):
    def __init__(self, users: list[User]) -> None:
        self._users = users
        self.created: list[User] = []
        self.reset_calls: list[tuple[Any, str]] = []

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users if u.email == email), None)

    async def reset_password(self, user_id: Any, password_hash: str) -> None:
        self.reset_calls.append((user_id, password_hash))
        for u in self._users:
            if u.id == user_id:
                u.password_hash = password_hash
                u.must_change_password = True
                break

    async def get_by_id(self, user_id: Any) -> User | None:
        return next((u for u in self._users if u.id == user_id), None)

    async def create(
        self, *, email: str, username: str, password_hash: str, quota_bytes: int
    ) -> User:
        now = datetime.now(UTC)
        u = User(
            id=uuid4(),
            email=email,
            username=username,
            password_hash=password_hash,
            avatar_url=None,
            quota_bytes=quota_bytes,
            used_bytes=0,
            is_active=True,
            is_admin=False,
            must_change_password=False,
            created_at=now,
            updated_at=now,
        )
        self._users.append(u)
        self.created.append(u)
        return u


class FakeRTRepo(AbstractRefreshTokenRepository):
    def __init__(self) -> None:
        self._tokens: list[RefreshToken] = []

    async def create(self, *, user_id: Any, token_hash: str, expires_at: datetime) -> RefreshToken:

        rt = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_at=datetime.now(UTC),
        )
        self._tokens.append(rt)
        return rt

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self._tokens if t.token_hash == token_hash), None)

    async def revoke(self, token_id: Any) -> None:
        for t in self._tokens:
            if t.id == token_id:
                t.revoked_at = datetime.now(UTC)


# ── Test app factory ─────────────────────────────────────────────────────────


def _make_test_app(users: list[User] | None = None) -> tuple[FastAPI, FakeUserRepo, FakeRTRepo]:
    user_repo = FakeUserRepo(users or [])
    rt_repo = FakeRTRepo()
    service = AuthService(user_repo=user_repo, refresh_token_repo=rt_repo)

    from fastapi.responses import JSONResponse

    from app.auth.router import _make_service
    from app.core.exceptions import AppError

    app = FastAPI()

    @app.exception_handler(AppError)
    async def _app_error(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": str(exc.code), "message": exc.message, "details": exc.details}
            },
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_make_service] = lambda: service

    app.include_router(auth_router)
    return app, user_repo, rt_repo


@pytest.fixture()
def existing_user() -> User:
    return _user(email="existing@example.com", password="password123")


@pytest.fixture()
async def client(existing_user: User) -> AsyncGenerator[AsyncClient, None]:
    app, _, _ = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ── Register ─────────────────────────────────────────────────────────────────


async def test_register_success() -> None:
    app, repo, _ = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/register",
            json={"email": "new@example.com", "username": "alice", "password": "password123"},
        )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    assert "password_hash" not in body
    assert len(repo.created) == 1
    # refresh token cookie must be set
    assert "refresh_token" in resp.cookies


async def test_register_duplicate_email_returns_409(existing_user: User) -> None:
    app, _, _ = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/register",
            json={"email": existing_user.email, "username": "bob", "password": "password123"},
        )
    assert resp.status_code == 409


async def test_register_email_normalized() -> None:
    app, repo, _ = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/register",
            json={"email": "  UPPER@Example.COM  ", "username": "u", "password": "password123"},
        )
    assert resp.status_code == 201
    assert "access_token" in resp.json()
    assert repo.created[0].email == "upper@example.com"


# ── Login ─────────────────────────────────────────────────────────────────────


async def test_login_success(existing_user: User) -> None:
    app, _, _ = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/login", json={"email": existing_user.email, "password": "password123"}
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" not in body  # must NOT appear in body
    assert "refresh_token" in resp.cookies
    set_cookie = resp.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    assert "Secure" not in set_cookie


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_local_environments_allow_http_refresh_cookie(app_env: str) -> None:
    assert _is_secure_cookie_environment(app_env) is False


@pytest.mark.parametrize("app_env", ["staging", "production", "PRODUCTION"])
def test_deployed_environments_require_secure_refresh_cookie(app_env: str) -> None:
    assert _is_secure_cookie_environment(app_env) is True


async def test_login_wrong_password(existing_user: User) -> None:
    app, _, _ = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            "/auth/login", json={"email": existing_user.email, "password": "wrongpass"}
        )
    assert resp.status_code == 401


# ── Refresh ───────────────────────────────────────────────────────────────────


async def test_refresh_success(existing_user: User) -> None:
    app, _, _ = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login_resp = await c.post(
            "/auth/login", json={"email": existing_user.email, "password": "password123"}
        )
        old_rt = login_resp.cookies["refresh_token"]

        refresh_resp = await c.post("/auth/refresh", cookies={"refresh_token": old_rt})

    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    assert "refresh_token" in refresh_resp.cookies
    assert refresh_resp.cookies["refresh_token"] != old_rt


async def test_refresh_without_cookie_returns_401() -> None:
    app, _, _ = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/refresh")
    assert resp.status_code == 401


async def test_refresh_revoked_token_returns_401(existing_user: User) -> None:
    app, _, rt_repo = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login_resp = await c.post(
            "/auth/login", json={"email": existing_user.email, "password": "password123"}
        )
        rt_str = login_resp.cookies["refresh_token"]

        # Revoke the token
        for t in rt_repo._tokens:
            if t.token_hash == hash_token(rt_str):
                t.revoked_at = datetime.now(UTC)

        resp = await c.post("/auth/refresh", cookies={"refresh_token": rt_str})
    assert resp.status_code == 401


# ── Logout ────────────────────────────────────────────────────────────────────


async def test_logout_revokes_token(existing_user: User) -> None:
    app, _, rt_repo = _make_test_app([existing_user])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        login_resp = await c.post(
            "/auth/login", json={"email": existing_user.email, "password": "password123"}
        )
        rt_str = login_resp.cookies["refresh_token"]

        logout_resp = await c.post("/auth/logout", cookies={"refresh_token": rt_str})

    assert logout_resp.status_code == 204
    rt = await rt_repo.get_by_hash(hash_token(rt_str))
    assert rt is not None
    assert rt.revoked_at is not None
    assert "Path=/api/v1/auth" in logout_resp.headers["set-cookie"]


# ── /me ───────────────────────────────────────────────────────────────────────


async def test_me_requires_auth() -> None:
    app, _, _ = _make_test_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/auth/me")
    assert resp.status_code in (401, 403)  # HTTPBearer returns 403 (auto_error) or 401


async def test_me_returns_user(existing_user: User) -> None:
    app, _, _ = _make_test_app([existing_user])
    access_token = create_access_token(existing_user.id)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == existing_user.email
    assert "password_hash" not in body


# ── Forgot password ─────────────────────────────────────────────────────────


class _SpyEmailProvider:
    def __init__(self) -> None:
        self.sent: list[dict[str, str]] = []

    async def send(self, *, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


def _with_email_spy(app: FastAPI) -> _SpyEmailProvider:
    from app.email.factory import get_email_provider

    spy = _SpyEmailProvider()
    app.dependency_overrides[get_email_provider] = lambda: spy
    return spy


async def test_forgot_password_existing_email_resets_and_sends(existing_user: User) -> None:
    app, repo, _ = _make_test_app([existing_user])
    spy = _with_email_spy(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/forgot-password", json={"email": existing_user.email})
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert len(repo.reset_calls) == 1
    assert existing_user.must_change_password is True
    assert len(spy.sent) == 1
    assert spy.sent[0]["to"] == existing_user.email


async def test_forgot_password_unknown_email_returns_same_response() -> None:
    app, repo, _ = _make_test_app([])
    spy = _with_email_spy(app)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    # Non-enumerable: same 200 + message, but nothing actually happens.
    assert resp.status_code == 200
    assert "message" in resp.json()
    assert repo.reset_calls == []
    assert spy.sent == []
