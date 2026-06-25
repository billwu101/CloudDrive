from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.dependencies import get_db
from app.core.security import create_access_token
from app.external_model.crypto import CredentialCipher
from app.external_model.router import _connection_service
from app.external_model.router import router as ext_router
from app.external_model.service import ExternalModelConnectionService
from tests.external_model.test_service import MemConnectionRepo

pytestmark = pytest.mark.asyncio

_PREFIX = "/users/me/model-connections"


def _service(
    repo: MemConnectionRepo, *, with_cipher: bool = True
) -> ExternalModelConnectionService:
    cipher = CredentialCipher(Fernet.generate_key().decode()) if with_cipher else None
    return ExternalModelConnectionService(repo=repo, cipher=cipher, settings=get_settings())


def _make_app(service: ExternalModelConnectionService) -> FastAPI:
    app = FastAPI()

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_connection_service] = lambda: service
    app.include_router(ext_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def test_create_then_get_returns_masked_only(headers: dict[str, str]) -> None:
    app = _make_app(_service(MemConnectionRepo()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        created = await c.post(
            _PREFIX,
            json={
                "label": "My Gemini",
                "kind": "openai_compatible",
                "base_url": "https://g/v1",
                "model": "gemini-2.5-flash-lite",
                "secret": "sk-abcdef1234",
            },
            headers=headers,
        )
        listed = await c.get(_PREFIX, headers=headers)

    assert created.status_code == 200
    body = created.json()
    assert body["label"] == "My Gemini" and body["kind"] == "openai_compatible"
    assert body["masked_hint"].endswith("1234")
    assert "secret" not in body and "secret_encrypted" not in body  # never plaintext

    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1 and rows[0]["model"] == "gemini-2.5-flash-lite"
    assert "secret_encrypted" not in rows[0]


async def test_create_503_when_not_configured(headers: dict[str, str]) -> None:
    app = _make_app(_service(MemConnectionRepo(), with_cipher=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.post(
            _PREFIX,
            json={"label": "x", "kind": "openai_compatible", "secret": "sk-x"},
            headers=headers,
        )
    assert resp.status_code == 503


async def test_update_and_delete(user_id: UUID, headers: dict[str, str]) -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    conn = await svc.create(
        user_id=user_id,
        label="Old",
        kind="openai_compatible",
        base_url="b",
        model="m",
        secret="s",
    )
    app = _make_app(svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        updated = await c.put(f"{_PREFIX}/{conn.id}", json={"label": "New"}, headers=headers)
        deleted = await c.delete(f"{_PREFIX}/{conn.id}", headers=headers)

    assert updated.status_code == 200 and updated.json()["label"] == "New"
    assert deleted.status_code == 204
    assert await svc.list_masked(user_id) == []


async def test_update_missing_returns_404(headers: dict[str, str]) -> None:
    app = _make_app(_service(MemConnectionRepo()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(f"{_PREFIX}/{uuid4()}", json={"label": "x"}, headers=headers)
    assert resp.status_code == 404


async def test_requires_auth() -> None:
    app = _make_app(_service(MemConnectionRepo()))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(_PREFIX)
    assert resp.status_code in (401, 403)
