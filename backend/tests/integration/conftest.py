from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator, Generator

# Create storage temp dir and configure settings BEFORE any app imports.
# get_settings() uses @lru_cache, so the env var must be set first.
_STORAGE_DIR = tempfile.mkdtemp(prefix="clouddrive_int_storage_")
os.environ["LOCAL_STORAGE_PATH"] = _STORAGE_DIR

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.main import create_app
from app.models import Base

# Clear any previously cached settings so new LOCAL_STORAGE_PATH is used.
get_settings.cache_clear()


# Set by tests/conftest.py (which derives it from .env when the developer runs
# Postgres on a non-default port); an explicit DATABASE_URL still wins.
_TEST_DB_URL = os.environ["DATABASE_URL"]

_engine = create_async_engine(_TEST_DB_URL, echo=False, pool_pre_ping=True, poolclass=NullPool)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema() -> AsyncGenerator[None, None]:
    """Create all tables once per test session, drop them at the end."""
    async with _engine.begin() as conn:
        # file_embeddings uses the pgvector `vector` type; the CREATE EXTENSION
        # normally lives in migration 0012, but create_all does not run migrations.
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    shutil.rmtree(_STORAGE_DIR, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables() -> AsyncGenerator[None, None]:
    """Truncate all tables between tests for isolation."""
    yield
    async with _engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f'TRUNCATE TABLE "{table.name}" RESTART IDENTITY CASCADE'))


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Return an AsyncClient wired to the real FastAPI app with test DB."""
    app: FastAPI = create_app()

    async def _override_db() -> AsyncGenerator[AsyncSession, None]:
        async with _SessionFactory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────────


async def register_and_login(
    client: AsyncClient,
    *,
    email: str = "alice@example.com",
    username: str = "alice",
    password: str = "Password123!",
) -> str:
    """Register a user and return a valid access token.

    The registration response is checked, and the token is confirmed to belong
    to the requested email. Without that, a registration that silently 409s on
    the *username* unique key would leave the caller holding a token for some
    earlier user, and the test would go on to pass while exercising the wrong
    account entirely.
    """
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    assert registered.status_code in (200, 201, 409), registered.text

    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    token = str(resp.json()["access_token"])

    me = await client.get("/api/v1/users/me", headers=auth_headers(token))
    assert me.status_code == 200, me.text
    assert me.json()["email"] == email, (
        f"token belongs to {me.json()['email']!r}, not the requested {email!r} "
        "— the registration probably collided on the username"
    )
    return token


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
