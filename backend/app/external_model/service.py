from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMClient,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
    LLMUnavailableError,
)
from app.assistant.llm.external import ExternalLLMClient
from app.core.config import Settings
from app.external_model.codex_client import CodexSubscriptionClient
from app.external_model.crypto import CredentialCipher, CredentialCipherError, mask_secret
from app.external_model.repository import AbstractExternalCredentialRepository
from app.models.user_external_credential import UserExternalCredential

logger = logging.getLogger("app.external_model.service")


class _CredentialTrackingClient:
    """Wraps an external client; when a call is rejected for the credential
    itself (invalid key / exhausted quota), marks that credential invalid so the
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


class _FallbackClient:
    """Tries the primary client; on a credential rejection or outage, falls back
    to the secondary. Used for subscription-first → API-key fallback (§2.3)."""

    def __init__(self, primary: LLMClient, secondary: LLMClient) -> None:
        self._primary = primary
        self._secondary = secondary

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        try:
            return await self._primary.chat(
                messages, tools, num_ctx=num_ctx, response_format=response_format
            )
        except (ExternalAuthError, LLMUnavailableError):
            logger.info("external primary failed; falling back to secondary provider")
            return await self._secondary.chat(
                messages, tools, num_ctx=num_ctx, response_format=response_format
            )


class ExternalCredentialService:
    """Manages a user's encrypted external-model credentials and builds an
    LLM client from them for execution upgrade."""

    def __init__(
        self,
        *,
        repo: AbstractExternalCredentialRepository,
        cipher: CredentialCipher | None,
        settings: Settings,
        on_invalidate: Callable[[UUID, str], Awaitable[None]] | None = None,
        on_refresh: Callable[[UUID, str, str], Awaitable[None]] | None = None,
    ) -> None:
        self._repo = repo
        # None when CREDENTIAL_ENCRYPTION_KEY isn't configured (feature disabled).
        self._cipher = cipher
        self._settings = settings
        # Called (out of band, own session) to mark a credential invalid when the
        # provider rejects it during an actual upgrade call.
        self._on_invalidate = on_invalidate
        # Called (out of band) with (user_id, provider, new_secret) when a Codex
        # token is refreshed during a call, so it can be re-encrypted and stored.
        self._on_refresh = on_refresh

    @property
    def enabled(self) -> bool:
        return self._cipher is not None

    async def list_masked(self, user_id: UUID) -> list[UserExternalCredential]:
        return await self._repo.list_by_user(user_id)

    async def upsert(
        self, *, user_id: UUID, provider: str, auth_type: str, secret: str
    ) -> UserExternalCredential:
        if self._cipher is None:
            raise CredentialCipherError("external credentials are not configured on this server")
        await self._repo.upsert(
            user_id=user_id,
            provider=provider,
            auth_type=auth_type,
            secret_encrypted=self._cipher.encrypt(secret),
            masked_hint=mask_secret(secret),
            updated_at=datetime.now(UTC),
        )
        stored = await self._repo.get(user_id, provider)
        assert stored is not None  # just upserted
        return stored

    async def delete(self, user_id: UUID, provider: str) -> None:
        await self._repo.delete(user_id, provider)

    async def mark_invalid(self, user_id: UUID, provider: str) -> None:
        await self._repo.set_status(user_id, provider, "invalid")

    async def build_chat_client(self, user_id: UUID) -> LLMClient | None:
        """An external LLM client from the user's active credentials, or None.

        Subscription (codex) takes precedence; if the user also has an OpenAI key,
        the two are chained so a failing subscription falls back to the API key
        (§2.3). Decryption failures are skipped, not fatal.
        """
        if self._cipher is None:
            return None
        active = {
            c.provider: c for c in await self._repo.list_by_user(user_id) if c.status == "active"
        }
        codex = self._build_codex(active.get("codex"), user_id)
        openai = self._build_openai(active.get("openai"), user_id)
        if codex is not None and openai is not None:
            return _FallbackClient(codex, openai)
        return codex or openai

    async def active_providers(self, user_id: UUID) -> set[str]:
        """Provider names the user can explicitly select right now (active +
        decryptable). Empty when credentials are disabled or none are set."""
        return set((await self.build_provider_clients(user_id)).keys())

    async def build_provider_clients(self, user_id: UUID) -> dict[str, LLMClient]:
        """One client per active provider, keyed by provider name — for explicit
        model selection (no codex→openai chaining). Empty when disabled."""
        if self._cipher is None:
            return {}
        active = {
            c.provider: c for c in await self._repo.list_by_user(user_id) if c.status == "active"
        }
        clients: dict[str, LLMClient] = {}
        codex = self._build_codex(active.get("codex"), user_id)
        if codex is not None:
            clients["codex"] = codex
        openai = self._build_openai(active.get("openai"), user_id)
        if openai is not None:
            clients["openai"] = openai
        return clients

    def _decrypt(self, cred: UserExternalCredential, user_id: UUID) -> str | None:
        assert self._cipher is not None
        try:
            return self._cipher.decrypt(cred.secret_encrypted)
        except CredentialCipherError:
            logger.exception("failed to decrypt %s credential for user %s", cred.provider, user_id)
            return None

    def _build_openai(self, cred: UserExternalCredential | None, user_id: UUID) -> LLMClient | None:
        if cred is None or cred.auth_type != "api_key":
            return None
        key = self._decrypt(cred, user_id)
        if key is None:
            return None
        inner = ExternalLLMClient(
            base_url=self._settings.external_api_base_url,
            model=self._settings.external_chat_model,
            api_key=key,
        )
        return self._track(inner, user_id, "openai")

    def _build_codex(self, cred: UserExternalCredential | None, user_id: UUID) -> LLMClient | None:
        if cred is None or cred.auth_type != "oauth_token":
            return None
        auth_json = self._decrypt(cred, user_id)
        if auth_json is None:
            return None

        async def _on_refreshed(new_auth: str) -> None:
            if self._on_refresh is not None:
                await self._on_refresh(user_id, "codex", new_auth)

        inner = CodexSubscriptionClient(
            auth_json=auth_json,
            model=self._settings.external_chat_model,
            codex_bin=self._settings.codex_bin,
            on_refreshed=_on_refreshed,
        )
        return self._track(inner, user_id, "codex")

    def _track(self, inner: LLMClient, user_id: UUID, provider: str) -> LLMClient:
        """Wrap so a credential rejection during an upgrade call marks it invalid."""

        async def _on_auth_error() -> None:
            if self._on_invalidate is not None:
                await self._on_invalidate(user_id, provider)

        return _CredentialTrackingClient(inner, on_auth_error=_on_auth_error)
