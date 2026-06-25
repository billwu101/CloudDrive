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
from app.external_model.router import _credential_service
from app.external_model.router import router as ext_router
from app.external_model.service import ExternalCredentialService
from tests.external_model.test_service import MemCredentialRepo

pytestmark = pytest.mark.asyncio

_PREFIX = "/users/me/external-credentials"


def _service(*, with_cipher: bool = True) -> ExternalCredentialService:
    cipher = CredentialCipher(Fernet.generate_key().decode()) if with_cipher else None
    return ExternalCredentialService(
        repo=MemCredentialRepo(), cipher=cipher, settings=get_settings()
    )


def _make_app(service: ExternalCredentialService) -> FastAPI:
    app = FastAPI()

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_credential_service] = lambda: service
    app.include_router(ext_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def test_put_then_get_returns_masked_only(headers: dict[str, str]) -> None:
    service = _service()
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        put = await c.put(
            _PREFIX,
            json={"provider": "openai", "auth_type": "api_key", "secret": "sk-abcdef1234"},
            headers=headers,
        )
        get = await c.get(_PREFIX, headers=headers)

    assert put.status_code == 200
    body = put.json()
    assert body["provider"] == "openai"
    assert body["masked_hint"].endswith("1234")
    assert "secret" not in body and "secret_encrypted" not in body  # never plaintext

    assert get.status_code == 200
    rows = get.json()
    assert len(rows) == 1
    assert rows[0]["masked_hint"].endswith("1234")
    assert "secret_encrypted" not in rows[0]


async def test_put_503_when_credentials_not_configured(headers: dict[str, str]) -> None:
    app = _make_app(_service(with_cipher=False))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.put(
            _PREFIX,
            json={"provider": "openai", "auth_type": "api_key", "secret": "sk-x"},
            headers=headers,
        )
    assert resp.status_code == 503


async def test_delete_removes_credential(user_id: UUID, headers: dict[str, str]) -> None:
    service = _service()
    await service.upsert(user_id=user_id, provider="openai", auth_type="api_key", secret="sk-x")
    app = _make_app(service)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.delete(f"{_PREFIX}/openai", headers=headers)
    assert resp.status_code == 204
    assert await service.list_masked(user_id) == []


async def test_requires_auth() -> None:
    app = _make_app(_service())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(_PREFIX)
    assert resp.status_code in (401, 403)
