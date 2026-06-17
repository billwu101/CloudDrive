from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserId, DbSession
from app.core.exceptions import NotFoundError
from app.snapshot.repository import SQLSnapshotRepository
from app.snapshot.schemas import (
    CreateSnapshotRequest,
    SnapshotEntryResponse,
    SnapshotResponse,
)
from app.snapshot.service import TRIGGER_MANUAL, SnapshotService

router = APIRouter(prefix="/snapshots", tags=["time-machine"])


def _snapshot_service(session: DbSession) -> SnapshotService:
    return SnapshotService(repo=SQLSnapshotRepository(session))


SnapshotServiceDep = Annotated[SnapshotService, Depends(_snapshot_service)]


@router.post("", response_model=SnapshotResponse, summary="Create a snapshot now")
async def create_snapshot(
    body: CreateSnapshotRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: SnapshotServiceDep,
) -> SnapshotResponse:
    snapshot = await service.create(
        user_id=current_user_id, trigger=TRIGGER_MANUAL, label=body.label
    )
    await session.commit()
    return SnapshotResponse.model_validate(snapshot)


@router.get("", response_model=list[SnapshotResponse], summary="List snapshots (timeline)")
async def list_snapshots(
    current_user_id: CurrentUserId,
    service: SnapshotServiceDep,
) -> list[SnapshotResponse]:
    snapshots = await service.list_snapshots(user_id=current_user_id)
    return [SnapshotResponse.model_validate(s) for s in snapshots]


@router.get(
    "/{snapshot_id}/items",
    response_model=list[SnapshotEntryResponse],
    summary="Browse a folder inside a snapshot (read-only)",
)
async def list_snapshot_items(
    snapshot_id: UUID,
    current_user_id: CurrentUserId,
    service: SnapshotServiceDep,
    parent_id: UUID | None = None,
) -> list[SnapshotEntryResponse]:
    entries = await service.browse(
        user_id=current_user_id, snapshot_id=snapshot_id, parent_item_id=parent_id
    )
    if entries is None:
        raise NotFoundError("Snapshot not found")
    return [SnapshotEntryResponse.model_validate(e) for e in entries]
