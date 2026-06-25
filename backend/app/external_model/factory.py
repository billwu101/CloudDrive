from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.external_model.crypto import CredentialCipher, mask_secret
from app.external_model.repository import SQLExternalCredentialRepository
from app.external_model.service import ExternalCredentialService


def build_credential_service(
    session: AsyncSession, settings: Settings
) -> ExternalCredentialService:
    cipher = (
        CredentialCipher(settings.credential_encryption_key)
        if settings.credential_encryption_key
        else None
    )

    async def _invalidate(user_id: UUID, provider: str) -> None:
        # Use a fresh session so the invalid status persists even if the request
        # that triggered the failed upgrade rolls back.
        from app.db.base import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await SQLExternalCredentialRepository(s).set_status(user_id, provider, "invalid")
            await s.commit()

    async def _refresh(user_id: UUID, provider: str, new_secret: str) -> None:
        # Re-encrypt and store a Codex token the CLI refreshed mid-call, in its
        # own session, so the next call uses the fresh token.
        if cipher is None:
            return
        from app.db.base import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await SQLExternalCredentialRepository(s).upsert(
                user_id=user_id,
                provider=provider,
                auth_type="oauth_token",
                secret_encrypted=cipher.encrypt(new_secret),
                masked_hint=mask_secret(new_secret),
                updated_at=datetime.now(UTC),
            )
            await s.commit()

    return ExternalCredentialService(
        repo=SQLExternalCredentialRepository(session),
        cipher=cipher,
        settings=settings,
        on_invalidate=_invalidate,
        on_refresh=_refresh,
    )
