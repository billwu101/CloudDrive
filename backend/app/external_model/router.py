from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.external_model.crypto import CredentialCipher, CredentialCipherError
from app.external_model.repository import SQLExternalCredentialRepository
from app.external_model.schemas import ExternalCredentialUpsert, ExternalCredentialView
from app.external_model.service import ExternalCredentialService

router = APIRouter(prefix="/users/me/external-credentials", tags=["external-model"])


def _credential_service(session: DbSession) -> ExternalCredentialService:
    settings = get_settings()
    cipher = (
        CredentialCipher(settings.credential_encryption_key)
        if settings.credential_encryption_key
        else None
    )
    return ExternalCredentialService(
        repo=SQLExternalCredentialRepository(session), cipher=cipher, settings=settings
    )


ServiceDep = Annotated[ExternalCredentialService, Depends(_credential_service)]


@router.get(
    "", response_model=list[ExternalCredentialView], summary="List my external credentials (masked)"
)
async def list_credentials(
    current_user_id: CurrentUserId,
    service: ServiceDep,
) -> list[ExternalCredentialView]:
    creds = await service.list_masked(current_user_id)
    return [ExternalCredentialView.model_validate(c) for c in creds]


@router.put(
    "",
    response_model=ExternalCredentialView,
    summary="Set/replace an external credential (stored encrypted)",
    responses={503: {"description": "External credentials are not configured on this server"}},
)
async def upsert_credential(
    body: ExternalCredentialUpsert,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: ServiceDep,
) -> ExternalCredentialView:
    try:
        stored = await service.upsert(
            user_id=current_user_id,
            provider=body.provider,
            auth_type=body.auth_type,
            secret=body.secret,
        )
    except CredentialCipherError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.commit()
    return ExternalCredentialView.model_validate(stored)


@router.delete(
    "/{provider}",
    status_code=204,
    summary="Remove an external credential",
)
async def delete_credential(
    provider: str,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: ServiceDep,
) -> None:
    await service.delete(current_user_id, provider)
    await session.commit()
