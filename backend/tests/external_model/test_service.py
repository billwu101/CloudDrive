from __future__ import annotations

from datetime import UTC, datetime
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
from app.core.config import get_settings
from app.external_model.crypto import CredentialCipher
from app.external_model.repository import AbstractExternalCredentialRepository
from app.external_model.service import ExternalCredentialService, _CredentialTrackingClient
from app.models.user_external_credential import UserExternalCredential


class MemCredentialRepo(AbstractExternalCredentialRepository):
    def __init__(self) -> None:
        self.rows: dict[tuple[UUID, str], UserExternalCredential] = {}

    async def list_by_user(self, user_id: UUID) -> list[UserExternalCredential]:
        return [c for (u, _p), c in self.rows.items() if u == user_id]

    async def get(self, user_id: UUID, provider: str) -> UserExternalCredential | None:
        return self.rows.get((user_id, provider))

    async def upsert(
        self,
        *,
        user_id: UUID,
        provider: str,
        auth_type: str,
        secret_encrypted: str,
        masked_hint: str,
        updated_at: datetime,
    ) -> None:
        self.rows[(user_id, provider)] = UserExternalCredential(
            user_id=user_id,
            provider=provider,
            auth_type=auth_type,
            secret_encrypted=secret_encrypted,
            masked_hint=masked_hint,
            status="active",
            updated_at=updated_at,
        )

    async def delete(self, user_id: UUID, provider: str) -> None:
        self.rows.pop((user_id, provider), None)

    async def set_status(self, user_id: UUID, provider: str, status: str) -> None:
        row = self.rows.get((user_id, provider))
        if row is not None:
            row.status = status


def _service(repo: MemCredentialRepo, *, with_cipher: bool = True) -> ExternalCredentialService:
    cipher = CredentialCipher(Fernet.generate_key().decode()) if with_cipher else None
    return ExternalCredentialService(repo=repo, cipher=cipher, settings=get_settings())


async def test_upsert_encrypts_and_masks() -> None:
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()

    stored = await svc.upsert(
        user_id=user, provider="openai", auth_type="api_key", secret="sk-abcdef123456"
    )

    assert stored.secret_encrypted != "sk-abcdef123456"  # encrypted at rest
    assert stored.masked_hint.endswith("3456")
    assert stored.status == "active"


async def test_build_chat_client_openai_api_key() -> None:
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()
    await svc.upsert(user_id=user, provider="openai", auth_type="api_key", secret="sk-key-9999")

    client = await svc.build_chat_client(user)

    # Wrapped so a credential rejection can mark it invalid; inner is the real client.
    assert isinstance(client, _CredentialTrackingClient)
    inner = client._inner
    assert isinstance(inner, ExternalLLMClient)
    assert inner._api_key == "sk-key-9999"  # decrypted for use
    assert inner._model == get_settings().external_chat_model


async def test_build_chat_client_none_without_credentials() -> None:
    assert await _service(MemCredentialRepo()).build_chat_client(uuid4()) is None


async def test_build_chat_client_none_when_cipher_disabled() -> None:
    repo = MemCredentialRepo()
    user = uuid4()
    # Seed a row directly; service has no cipher so it can't use it.
    repo.rows[(user, "openai")] = UserExternalCredential(
        user_id=user,
        provider="openai",
        auth_type="api_key",
        secret_encrypted="whatever",
        masked_hint="…",
        status="active",
        updated_at=datetime.now(UTC),
    )
    assert await _service(repo, with_cipher=False).build_chat_client(user) is None


async def test_build_chat_client_skips_invalid_status() -> None:
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()
    await svc.upsert(user_id=user, provider="openai", auth_type="api_key", secret="sk-x")
    await svc.mark_invalid(user, "openai")

    assert await svc.build_chat_client(user) is None


async def test_subscription_preferred_falls_back_to_openai_until_e3() -> None:
    # A user with both a (not-yet-implemented) codex token and an openai key gets
    # the openai client for now — codex (E3) is skipped, not an error.
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()
    await svc.upsert(user_id=user, provider="codex", auth_type="oauth_token", secret="tok")
    await svc.upsert(user_id=user, provider="openai", auth_type="api_key", secret="sk-fallback")

    client = await svc.build_chat_client(user)
    assert isinstance(client, _CredentialTrackingClient)
    assert isinstance(client._inner, ExternalLLMClient)
    assert client._inner._api_key == "sk-fallback"


# ── credential-tracking wrapper (auto-mark invalid on rejection) ──────────────


class _BoomAuth:
    async def chat(
        self, messages: list[LLMMessage], tools: list[LLMToolDefinition], *, num_ctx: int
    ) -> LLMResponse:
        raise ExternalAuthError("credential rejected")


class _BoomTransient:
    async def chat(
        self, messages: list[LLMMessage], tools: list[LLMToolDefinition], *, num_ctx: int
    ) -> LLMResponse:
        raise LLMUnavailableError("temporary outage")


class _Ok:
    async def chat(
        self, messages: list[LLMMessage], tools: list[LLMToolDefinition], *, num_ctx: int
    ) -> LLMResponse:
        return LLMResponse(content="ok")


async def test_tracking_marks_invalid_on_auth_error() -> None:
    called: list[bool] = []

    async def on_err() -> None:
        called.append(True)

    client = _CredentialTrackingClient(_BoomAuth(), on_auth_error=on_err)
    with pytest.raises(ExternalAuthError):
        await client.chat([], [], num_ctx=10)
    assert called == [True]  # credential marked invalid


async def test_tracking_does_not_mark_on_transient_error() -> None:
    called: list[bool] = []

    async def on_err() -> None:
        called.append(True)

    client = _CredentialTrackingClient(_BoomTransient(), on_auth_error=on_err)
    with pytest.raises(LLMUnavailableError):
        await client.chat([], [], num_ctx=10)
    assert called == []  # transient outage must NOT invalidate the key


async def test_tracking_passes_through_success() -> None:
    called: list[bool] = []

    async def on_err() -> None:
        called.append(True)

    client = _CredentialTrackingClient(_Ok(), on_auth_error=on_err)
    resp = await client.chat([], [], num_ctx=10)
    assert resp.content == "ok"
    assert called == []


async def test_build_chat_client_wraps_with_invalidate_callback() -> None:
    invalidated: list[tuple[UUID, str]] = []

    async def on_invalidate(user_id: UUID, provider: str) -> None:
        invalidated.append((user_id, provider))

    repo = MemCredentialRepo()
    svc = ExternalCredentialService(
        repo=repo,
        cipher=CredentialCipher(Fernet.generate_key().decode()),
        settings=get_settings(),
        on_invalidate=on_invalidate,
    )
    user = uuid4()
    await svc.upsert(user_id=user, provider="openai", auth_type="api_key", secret="sk-x")
    client = await svc.build_chat_client(user)
    assert isinstance(client, _CredentialTrackingClient)

    # Force the wrapped client to see a credential rejection.
    client._inner = _BoomAuth()
    with pytest.raises(ExternalAuthError):
        await client.chat([], [], num_ctx=10)
    assert invalidated == [(user, "openai")]
