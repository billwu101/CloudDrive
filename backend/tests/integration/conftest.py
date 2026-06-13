from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncGenerator

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

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.main import create_app
from app.models import Base

# Clear any previously cached settings so new LOCAL_STORAGE_PATH is used.
get_settings.cache_clear()

_TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/clouddrive_test",
)

_engine = create_async_engine(_TEST_DB_URL, echo=False, pool_pre_ping=True)
_SessionFactory = async_sessionmaker(_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _create_schema():
    """Create all tables once per test session, drop them at the end."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    shutil.rmtree(_STORAGE_DIR, ignore_errors=True)


@pytest_asyncio.fixture(autouse=True)
async def _truncate_tables():
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

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as ac:
        yield ac


# ── Helpers ──────────────────────────────────────────────────────────────────


async def register_and_login(
    client: AsyncClient,
    *,
    email: str = "alice@example.com",
    username: str = "alice",
    password: str = "Password123!",
) -> str:
    """Register a user and return a valid access token."""
    await client.post(
        "/api/v1/auth/register",
        json={"email": email, "username": username, "password": password},
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
