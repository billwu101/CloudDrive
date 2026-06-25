from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.external_model.crypto import CredentialCipherError
from app.external_model.factory import build_connection_service
from app.external_model.schemas import ConnectionCreate, ConnectionUpdate, ConnectionView
from app.external_model.service import ExternalModelConnectionService

router = APIRouter(prefix="/users/me/model-connections", tags=["external-model"])


def _connection_service(session: DbSession) -> ExternalModelConnectionService:
    return build_connection_service(session, get_settings())


ServiceDep = Annotated[ExternalModelConnectionService, Depends(_connection_service)]


@router.get("", response_model=list[ConnectionView], summary="List my model connections (masked)")
async def list_connections(
    current_user_id: CurrentUserId,
    service: ServiceDep,
) -> list[ConnectionView]:
    conns = await service.list_masked(current_user_id)
    return [ConnectionView.model_validate(c) for c in conns]


@router.post(
    "",
    response_model=ConnectionView,
    summary="Add a model connection (stored encrypted)",
    responses={503: {"description": "External connections are not configured on this server"}},
)
async def create_connection(
    body: ConnectionCreate,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: ServiceDep,
) -> ConnectionView:
    try:
        stored = await service.create(
            user_id=current_user_id,
            label=body.label,
            kind=body.kind,
            base_url=body.base_url,
            model=body.model,
            secret=body.secret,
        )
    except CredentialCipherError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    await session.commit()
    return ConnectionView.model_validate(stored)


@router.put(
    "/{connection_id}",
    response_model=ConnectionView,
    summary="Edit a model connection",
    responses={503: {"description": "External connections are not configured on this server"}},
)
async def update_connection(
    connection_id: UUID,
    body: ConnectionUpdate,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: ServiceDep,
) -> ConnectionView:
    try:
        stored = await service.update(
            user_id=current_user_id,
            connection_id=connection_id,
            label=body.label,
            base_url=body.base_url,
            model=body.model,
            secret=body.secret,
        )
    except CredentialCipherError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if stored is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    await session.commit()
    return ConnectionView.model_validate(stored)


@router.delete("/{connection_id}", status_code=204, summary="Remove a model connection")
async def delete_connection(
    connection_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: ServiceDep,
) -> None:
    await service.delete(current_user_id, connection_id)
    await session.commit()
