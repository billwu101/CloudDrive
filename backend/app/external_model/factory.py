from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.external_model.crypto import CredentialCipher
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

    return ExternalCredentialService(
        repo=SQLExternalCredentialRepository(session),
        cipher=cipher,
        settings=settings,
        on_invalidate=_invalidate,
    )
