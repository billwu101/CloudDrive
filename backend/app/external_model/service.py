from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import UUID

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMClient,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
)
from app.assistant.llm.external import ExternalLLMClient
from app.core.config import Settings
from app.external_model.crypto import CredentialCipher, CredentialCipherError, mask_secret
from app.external_model.repository import AbstractExternalCredentialRepository
from app.models.user_external_credential import UserExternalCredential

logger = logging.getLogger("app.external_model.service")

# Provider preference when upgrading: subscription (codex) first, then API key
# (openai). E2 implements only "openai"; "codex" (E3) is skipped until built.
_PROVIDER_PREFERENCE = ("codex", "openai")


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
    ) -> LLMResponse:
        try:
            return await self._inner.chat(messages, tools, num_ctx=num_ctx)
        except ExternalAuthError:
            await self._on_auth_error()
            raise


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
    ) -> None:
        self._repo = repo
        # None when CREDENTIAL_ENCRYPTION_KEY isn't configured (feature disabled).
        self._cipher = cipher
        self._settings = settings
        # Called (out of band, own session) to mark a credential invalid when the
        # provider rejects it during an actual upgrade call.
        self._on_invalidate = on_invalidate

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

        Subscription (codex) takes precedence, then OpenAI API key. Decryption
        failures are skipped (not fatal) so one bad credential doesn't block all.
        """
        if self._cipher is None:
            return None
        active = {
            c.provider: c for c in await self._repo.list_by_user(user_id) if c.status == "active"
        }
        for provider in _PROVIDER_PREFERENCE:
            cred = active.get(provider)
            if cred is None:
                continue
            if provider == "openai" and cred.auth_type == "api_key":
                try:
                    key = self._cipher.decrypt(cred.secret_encrypted)
                except CredentialCipherError:
                    logger.exception("failed to decrypt openai credential for user %s", user_id)
                    continue
                inner = ExternalLLMClient(
                    base_url=self._settings.external_api_base_url,
                    model=self._settings.external_chat_model,
                    api_key=key,
                )
                return self._track(inner, user_id, "openai")
            # provider == "codex" → E3 (Codex subscription) not implemented yet.
        return None

    def _track(self, inner: LLMClient, user_id: UUID, provider: str) -> LLMClient:
        """Wrap so a credential rejection during an upgrade call marks it invalid."""

        async def _on_auth_error() -> None:
            if self._on_invalidate is not None:
                await self._on_invalidate(user_id, provider)

        return _CredentialTrackingClient(inner, on_auth_error=_on_auth_error)
