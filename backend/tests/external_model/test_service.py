from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from cryptography.fernet import Fernet

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
    LLMUnavailableError,
)
from app.assistant.llm.external import ExternalLLMClient
from app.assistant.llm.ollama import OllamaLLMClient
from app.core.config import get_settings
from app.external_model.codex_client import CodexSubscriptionClient
from app.external_model.crypto import CredentialCipher
from app.external_model.repository import AbstractConnectionRepository
from app.external_model.service import (
    ExternalModelConnectionService,
    _CredentialTrackingClient,
)
from app.models.external_model_connection import ExternalModelConnection


class MemConnectionRepo(AbstractConnectionRepository):
    def __init__(self) -> None:
        self.rows: dict[UUID, ExternalModelConnection] = {}

    async def list_by_user(self, user_id: UUID) -> list[ExternalModelConnection]:
        return [c for c in self.rows.values() if c.user_id == user_id]

    async def get(self, user_id: UUID, connection_id: UUID) -> ExternalModelConnection | None:
        conn = self.rows.get(connection_id)
        return conn if conn is not None and conn.user_id == user_id else None

    async def create(self, connection: ExternalModelConnection) -> ExternalModelConnection:
        self.rows[connection.id] = connection
        return connection

    async def update(
        self,
        *,
        user_id: UUID,
        connection_id: UUID,
        label: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        secret_encrypted: str | None = None,
        masked_hint: str | None = None,
        status: str | None = None,
        updated_at: datetime,
    ) -> ExternalModelConnection | None:
        conn = await self.get(user_id, connection_id)
        if conn is None:
            return None
        for field, value in (
            ("label", label),
            ("base_url", base_url),
            ("model", model),
            ("secret_encrypted", secret_encrypted),
            ("masked_hint", masked_hint),
            ("status", status),
        ):
            if value is not None:
                setattr(conn, field, value)
        conn.updated_at = updated_at
        return conn

    async def delete(self, user_id: UUID, connection_id: UUID) -> bool:
        conn = await self.get(user_id, connection_id)
        if conn is None:
            return False
        del self.rows[connection_id]
        return True

    async def set_status(self, user_id: UUID, connection_id: UUID, status: str) -> None:
        conn = await self.get(user_id, connection_id)
        if conn is not None:
            conn.status = status


def _service(
    repo: MemConnectionRepo, *, with_cipher: bool = True
) -> ExternalModelConnectionService:
    cipher = CredentialCipher(Fernet.generate_key().decode()) if with_cipher else None
    return ExternalModelConnectionService(repo=repo, cipher=cipher, settings=get_settings())


async def test_create_encrypts_and_masks() -> None:
    svc = _service(MemConnectionRepo())
    stored = await svc.create(
        user_id=uuid4(),
        label="My Gemini",
        kind="openai_compatible",
        base_url="https://example/v1",
        model="gemini-2.5-flash-lite",
        secret="sk-abcdef123456",
    )
    assert stored.secret_encrypted != "sk-abcdef123456"  # encrypted at rest
    assert stored.masked_hint.endswith("3456")
    assert stored.status == "active"


async def test_build_clients_openai_compatible() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user,
        label="Gemini",
        kind="openai_compatible",
        base_url="https://g/v1",
        model="gemini-2.5-flash-lite",
        secret="sk-key-9999",
    )

    clients = await svc.build_clients(user)

    assert set(clients) == {str(conn.id)}
    wrapper = clients[str(conn.id)]
    assert isinstance(wrapper, _CredentialTrackingClient)
    inner = wrapper._inner
    assert isinstance(inner, ExternalLLMClient)
    assert inner._api_key == "sk-key-9999"  # decrypted for use
    assert inner._model == "gemini-2.5-flash-lite"


async def test_build_clients_ollama_kind() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user,
        label="Ollama",
        kind="ollama",
        base_url="https://ollama/v1",
        model="llama3",
        secret="ok-123",
    )
    clients = await svc.build_clients(user)
    wrapper = clients[str(conn.id)]
    assert isinstance(wrapper, _CredentialTrackingClient)
    assert isinstance(wrapper._inner, OllamaLLMClient)


async def test_build_clients_codex_kind() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user, label="Codex", kind="codex", base_url="", model="", secret='{"tokens":{}}'
    )
    clients = await svc.build_clients(user)
    wrapper = clients[str(conn.id)]
    assert isinstance(wrapper, _CredentialTrackingClient)
    assert isinstance(wrapper._inner, CodexSubscriptionClient)


async def test_build_clients_empty_without_cipher() -> None:
    assert await _service(MemConnectionRepo(), with_cipher=False).build_clients(uuid4()) == {}


async def test_build_clients_skips_invalid() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user, label="X", kind="openai_compatible", base_url="b", model="m", secret="s"
    )
    await repo.set_status(user, conn.id, "invalid")
    assert await svc.build_clients(user) == {}


async def test_update_new_secret_reencrypts_and_clears_invalid() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user, label="X", kind="openai_compatible", base_url="b", model="m", secret="old"
    )
    await repo.set_status(user, conn.id, "invalid")

    updated = await svc.update(user_id=user, connection_id=conn.id, secret="new-secret-9876")

    assert updated is not None
    assert updated.status == "active"  # editing clears the invalid flag
    assert updated.masked_hint.endswith("9876")


async def test_delete_removes_connection() -> None:
    repo = MemConnectionRepo()
    svc = _service(repo)
    user = uuid4()
    conn = await svc.create(
        user_id=user, label="X", kind="openai_compatible", base_url="b", model="m", secret="s"
    )
    assert await svc.delete(user, conn.id) is True
    assert await svc.list_masked(user) == []


async def test_codex_refresh_flows_back_to_on_refresh() -> None:
    refreshed: list[tuple[UUID, UUID, str]] = []

    async def on_refresh(user_id: UUID, connection_id: UUID, secret: str) -> None:
        refreshed.append((user_id, connection_id, secret))

    repo = MemConnectionRepo()
    svc = ExternalModelConnectionService(
        repo=repo,
        cipher=CredentialCipher(Fernet.generate_key().decode()),
        settings=get_settings(),
        on_refresh=on_refresh,
    )
    user = uuid4()
    conn = await svc.create(
        user_id=user,
        label="Codex",
        kind="codex",
        base_url="",
        model="",
        secret='{"tokens":{"access_token":"OLD"}}',
    )
    wrapper = (await svc.build_clients(user))[str(conn.id)]
    assert isinstance(wrapper, _CredentialTrackingClient)
    codex = wrapper._inner
    assert isinstance(codex, CodexSubscriptionClient)

    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        with open(os.path.join(env["CODEX_HOME"], "auth.json"), "w", encoding="utf-8") as fh:
            fh.write('{"tokens":{"access_token":"NEW"}}')
        return 0, "x\ncodex\nok\ntokens used 1"

    codex._runner = runner
    await wrapper.chat([LLMMessage(role="user", content="x")], [], num_ctx=10)
    assert refreshed == [(user, conn.id, '{"tokens":{"access_token":"NEW"}}')]


# ── credential-tracking wrapper (auto-mark invalid on rejection) ──────────────


class _BoomAuth:
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        raise ExternalAuthError("credential rejected")


class _BoomTransient:
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        raise LLMUnavailableError("temporary outage")


class _Ok:
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="ok")


async def test_tracking_marks_invalid_on_auth_error() -> None:
    called: list[bool] = []

    async def on_err() -> None:
        called.append(True)

    client = _CredentialTrackingClient(_BoomAuth(), on_auth_error=on_err)
    with pytest.raises(ExternalAuthError):
        await client.chat([], [], num_ctx=10)
    assert called == [True]


async def test_tracking_does_not_mark_on_transient_error() -> None:
    called: list[bool] = []

    async def on_err() -> None:
        called.append(True)

    client = _CredentialTrackingClient(_BoomTransient(), on_auth_error=on_err)
    with pytest.raises(LLMUnavailableError):
        await client.chat([], [], num_ctx=10)
    assert called == []


async def test_tracking_passes_through_success() -> None:
    client = _CredentialTrackingClient(_Ok(), on_auth_error=lambda: _noop())
    resp = await client.chat([], [], num_ctx=10)
    assert resp.content == "ok"


async def _noop() -> None:
    return None


async def test_build_clients_wraps_with_invalidate_callback() -> None:
    invalidated: list[tuple[UUID, UUID]] = []

    async def on_invalidate(user_id: UUID, connection_id: UUID) -> None:
        invalidated.append((user_id, connection_id))

    repo = MemConnectionRepo()
    svc = ExternalModelConnectionService(
        repo=repo,
        cipher=CredentialCipher(Fernet.generate_key().decode()),
        settings=get_settings(),
        on_invalidate=on_invalidate,
    )
    user = uuid4()
    conn = await svc.create(
        user_id=user, label="X", kind="openai_compatible", base_url="b", model="m", secret="sk-x"
    )
    wrapper = (await svc.build_clients(user))[str(conn.id)]
    assert isinstance(wrapper, _CredentialTrackingClient)
    wrapper._inner = _BoomAuth()
    with pytest.raises(ExternalAuthError):
        await wrapper.chat([], [], num_ctx=10)
    assert invalidated == [(user, conn.id)]
