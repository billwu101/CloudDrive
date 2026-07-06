from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.external_model.crypto import CredentialCipher, mask_secret
from app.external_model.repository import SQLConnectionRepository
from app.external_model.service import ExternalModelConnectionService


def build_connection_service(
    session: AsyncSession, settings: Settings
) -> ExternalModelConnectionService:
    cipher = (
        CredentialCipher(settings.credential_encryption_key)
        if settings.credential_encryption_key
        else None
    )

    async def _invalidate(user_id: UUID, connection_id: UUID) -> None:
        # Fresh session so the invalid status persists even if the request that
        # triggered the failed upgrade rolls back.
        from app.db.base import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await SQLConnectionRepository(s).set_status(user_id, connection_id, "invalid")
            await s.commit()

    async def _refresh(user_id: UUID, connection_id: UUID, new_secret: str) -> None:
        # Re-encrypt and store a Codex token the CLI refreshed mid-call.
        if cipher is None:
            return
        from app.db.base import AsyncSessionLocal

        async with AsyncSessionLocal() as s:
            await SQLConnectionRepository(s).update(
                user_id=user_id,
                connection_id=connection_id,
                secret_encrypted=cipher.encrypt(new_secret),
                masked_hint=mask_secret(new_secret),
                updated_at=datetime.now(UTC),
            )
            await s.commit()

    return ExternalModelConnectionService(
        repo=SQLConnectionRepository(session),
        cipher=cipher,
        settings=settings,
        on_invalidate=_invalidate,
        on_refresh=_refresh,
    )
