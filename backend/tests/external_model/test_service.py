from __future__ import annotations

import os
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
from app.external_model.codex_client import CodexSubscriptionClient
from app.external_model.crypto import CredentialCipher
from app.external_model.repository import AbstractExternalCredentialRepository
from app.external_model.service import (
    ExternalCredentialService,
    _CredentialTrackingClient,
    _FallbackClient,
)
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


async def test_build_chat_client_codex_only() -> None:
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()
    await svc.upsert(
        user_id=user, provider="codex", auth_type="oauth_token", secret='{"tokens":{}}'
    )

    client = await svc.build_chat_client(user)
    assert isinstance(client, _CredentialTrackingClient)
    assert isinstance(client._inner, CodexSubscriptionClient)


async def test_subscription_first_chains_to_openai_fallback() -> None:
    # With both a Codex subscription and an OpenAI key, the subscription is tried
    # first and the key is the fallback (§2.3).
    repo = MemCredentialRepo()
    svc = _service(repo)
    user = uuid4()
    await svc.upsert(
        user_id=user, provider="codex", auth_type="oauth_token", secret='{"tokens":{}}'
    )
    await svc.upsert(user_id=user, provider="openai", auth_type="api_key", secret="sk-fallback")

    client = await svc.build_chat_client(user)
    assert isinstance(client, _FallbackClient)
    assert isinstance(client._primary, _CredentialTrackingClient)
    assert isinstance(client._primary._inner, CodexSubscriptionClient)  # codex tried first
    assert isinstance(client._secondary, _CredentialTrackingClient)
    assert isinstance(client._secondary._inner, ExternalLLMClient)
    assert client._secondary._inner._api_key == "sk-fallback"  # api key is the fallback


async def test_codex_refresh_flows_back_to_on_refresh() -> None:
    # A token refreshed by the CLI mid-call is handed to the service's on_refresh.
    refreshed: list[tuple[UUID, str, str]] = []

    async def on_refresh(user_id: UUID, provider: str, secret: str) -> None:
        refreshed.append((user_id, provider, secret))

    repo = MemCredentialRepo()
    svc = ExternalCredentialService(
        repo=repo,
        cipher=CredentialCipher(Fernet.generate_key().decode()),
        settings=get_settings(),
        on_refresh=on_refresh,
    )
    user = uuid4()
    await svc.upsert(
        user_id=user,
        provider="codex",
        auth_type="oauth_token",
        secret='{"tokens":{"access_token":"OLD"}}',
    )
    client = await svc.build_chat_client(user)
    assert isinstance(client, _CredentialTrackingClient)
    codex = client._inner
    assert isinstance(codex, CodexSubscriptionClient)

    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        with open(os.path.join(env["CODEX_HOME"], "auth.json"), "w", encoding="utf-8") as fh:
            fh.write('{"tokens":{"access_token":"NEW"}}')
        return 0, "x\ncodex\nok\ntokens used 1"

    codex._runner = runner
    await client.chat([LLMMessage(role="user", content="x")], [], num_ctx=10)
    assert refreshed == [(user, "codex", '{"tokens":{"access_token":"NEW"}}')]


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


# ── subscription-first fallback chain ────────────────────────────────────────


async def test_fallback_uses_secondary_on_transient_failure() -> None:
    client = _FallbackClient(_BoomTransient(), _Ok())
    resp = await client.chat([], [], num_ctx=10)
    assert resp.content == "ok"


async def test_fallback_uses_secondary_on_auth_error() -> None:
    client = _FallbackClient(_BoomAuth(), _Ok())
    resp = await client.chat([], [], num_ctx=10)
    assert resp.content == "ok"


async def test_fallback_returns_primary_when_it_succeeds() -> None:
    class _OkPrimary:
        async def chat(
            self, messages: list[LLMMessage], tools: list[LLMToolDefinition], *, num_ctx: int
        ) -> LLMResponse:
            return LLMResponse(content="primary")

    client = _FallbackClient(_OkPrimary(), _Ok())
    resp = await client.chat([], [], num_ctx=10)
    assert resp.content == "primary"  # secondary not used
