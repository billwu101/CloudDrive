from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMClient,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
)
from app.assistant.llm.external import ExternalLLMClient
from app.assistant.llm.ollama import OllamaLLMClient
from app.core.config import Settings
from app.external_model.codex_client import CodexSubscriptionClient
from app.external_model.crypto import CredentialCipher, CredentialCipherError, mask_secret
from app.external_model.repository import AbstractConnectionRepository
from app.models.external_model_connection import ExternalModelConnection

logger = logging.getLogger("app.external_model.service")


class _CredentialTrackingClient:
    """Wraps a connection's client; when a call is rejected for the credential
    itself (invalid key / exhausted quota), marks that connection invalid so the
    user sees it in settings, then re-raises. Transient outages don't mark it."""

    def __init__(self, inner: LLMClient, *, on_auth_error: Callable[[], Awaitable[None]]) -> None:
        self._inner = inner
        self._on_auth_error = on_auth_error

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            return await self._inner.chat(
                messages, tools, num_ctx=num_ctx, response_format=response_format
            )
        except ExternalAuthError:
            await self._on_auth_error()
            raise


class ExternalModelConnectionService:
    """Manages a user's named external-model connections and builds an LLM client
    from each for the assistant's model picker."""

    def __init__(
        self,
        *,
        repo: AbstractConnectionRepository,
        cipher: CredentialCipher | None,
        settings: Settings,
        on_invalidate: Callable[[UUID, UUID], Awaitable[None]] | None = None,
        on_refresh: Callable[[UUID, UUID, str], Awaitable[None]] | None = None,
    ) -> None:
        self._repo = repo
        # None when CREDENTIAL_ENCRYPTION_KEY isn't configured (feature disabled).
        self._cipher = cipher
        self._settings = settings
        self._on_invalidate = on_invalidate
        self._on_refresh = on_refresh

    @property
    def enabled(self) -> bool:
        return self._cipher is not None

    async def list_masked(self, user_id: UUID) -> list[ExternalModelConnection]:
        return await self._repo.list_by_user(user_id)

    async def create(
        self, *, user_id: UUID, label: str, kind: str, base_url: str, model: str, secret: str
    ) -> ExternalModelConnection:
        if self._cipher is None:
            raise CredentialCipherError("external connections are not configured on this server")
        now = datetime.now(UTC)
        conn = ExternalModelConnection(
            id=uuid4(),
            user_id=user_id,
            label=label,
            kind=kind,
            base_url=base_url,
            model=model,
            secret_encrypted=self._cipher.encrypt(secret),
            masked_hint=mask_secret(secret),
            status="active",
            created_at=now,
            updated_at=now,
        )
        return await self._repo.create(conn)

    async def update(
        self,
        *,
        user_id: UUID,
        connection_id: UUID,
        label: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        secret: str | None = None,
    ) -> ExternalModelConnection | None:
        if self._cipher is None:
            raise CredentialCipherError("external connections are not configured on this server")
        secret_encrypted = None
        masked_hint = None
        if secret is not None:
            secret_encrypted = self._cipher.encrypt(secret)
            masked_hint = mask_secret(secret)
        return await self._repo.update(
            user_id=user_id,
            connection_id=connection_id,
            label=label,
            base_url=base_url,
            model=model,
            secret_encrypted=secret_encrypted,
            masked_hint=masked_hint,
            # Editing a rejected connection clears its invalid flag.
            status="active" if secret is not None else None,
            updated_at=datetime.now(UTC),
        )

    async def delete(self, user_id: UUID, connection_id: UUID) -> bool:
        return await self._repo.delete(user_id, connection_id)

    async def build_clients(self, user_id: UUID) -> dict[str, LLMClient]:
        """One client per active, decryptable connection, keyed by ``str(id)`` —
        the assistant's model picker selects by this id. Empty when disabled."""
        if self._cipher is None:
            return {}
        clients: dict[str, LLMClient] = {}
        for conn in await self._repo.list_by_user(user_id):
            if conn.status != "active":
                continue
            client = self._build_client(conn)
            if client is not None:
                clients[str(conn.id)] = client
        return clients

    def _decrypt(self, conn: ExternalModelConnection) -> str | None:
        assert self._cipher is not None
        try:
            return self._cipher.decrypt(conn.secret_encrypted)
        except CredentialCipherError:
            logger.exception("failed to decrypt connection %s", conn.id)
            return None

    def _build_client(self, conn: ExternalModelConnection) -> LLMClient | None:
        secret = self._decrypt(conn)
        if secret is None:
            return None
        inner: LLMClient
        if conn.kind == "openai_compatible":
            inner = ExternalLLMClient(base_url=conn.base_url, model=conn.model, api_key=secret)
        elif conn.kind == "ollama":
            inner = OllamaLLMClient(base_url=conn.base_url, model=conn.model, api_key=secret)
        elif conn.kind == "codex":
            inner = self._build_codex(conn, secret)
        else:
            logger.warning("unknown connection kind %r for %s", conn.kind, conn.id)
            return None
        return self._track(inner, conn)

    def _build_codex(self, conn: ExternalModelConnection, auth_json: str) -> LLMClient:
        user_id, connection_id = conn.user_id, conn.id

        async def _on_refreshed(new_auth: str) -> None:
            if self._on_refresh is not None:
                await self._on_refresh(user_id, connection_id, new_auth)

        return CodexSubscriptionClient(
            auth_json=auth_json,
            model=conn.model or self._settings.external_chat_model,
            codex_bin=self._settings.codex_bin,
            on_refreshed=_on_refreshed,
        )

    def _track(self, inner: LLMClient, conn: ExternalModelConnection) -> LLMClient:
        user_id, connection_id = conn.user_id, conn.id

        async def _on_auth_error() -> None:
            if self._on_invalidate is not None:
                await self._on_invalidate(user_id, connection_id)

        return _CredentialTrackingClient(inner, on_auth_error=_on_auth_error)
