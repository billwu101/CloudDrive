from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.core.dependencies import CurrentUserId, DbSession
from app.core.exceptions import NotFoundError
from app.snapshot.repository import SQLSnapshotRepository
from app.snapshot.schemas import (
    CreateSnapshotRequest,
    RestoreRequest,
    RestoreResponse,
    SnapshotEntryResponse,
    SnapshotResponse,
    SnapshotSettingsResponse,
    UpdateSnapshotSettingsRequest,
)
from app.snapshot.service import TRIGGER_MANUAL, SnapshotService

router = APIRouter(prefix="/snapshots", tags=["time-machine"])


def _snapshot_service(session: DbSession) -> SnapshotService:
    return SnapshotService(
        repo=SQLSnapshotRepository(session),
        activity=ActivityLogService(SQLActivityLogRepository(session)),
    )


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


async def _settings_payload(service: SnapshotService, user_id: UUID) -> SnapshotSettingsResponse:
    settings = await service.get_settings(user_id=user_id)
    effective = await service.resolve_quota_bytes(user_id=user_id, settings=settings)
    used = await service.used_bytes(user_id=user_id)
    return SnapshotSettingsResponse(
        retention_n=settings.retention_n,
        schedule_enabled=settings.schedule_enabled,
        schedule_interval_minutes=settings.schedule_interval_minutes,
        quota_bytes=settings.quota_bytes,
        effective_quota_bytes=effective,
        used_bytes=used,
    )


@router.get(
    "/settings",
    response_model=SnapshotSettingsResponse,
    summary="Get Time Machine settings",
)
async def get_settings(
    current_user_id: CurrentUserId,
    service: SnapshotServiceDep,
) -> SnapshotSettingsResponse:
    return await _settings_payload(service, current_user_id)


@router.put(
    "/settings",
    response_model=SnapshotSettingsResponse,
    summary="Update Time Machine settings",
)
async def update_settings(
    body: UpdateSnapshotSettingsRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: SnapshotServiceDep,
) -> SnapshotSettingsResponse:
    await service.update_settings(
        user_id=current_user_id,
        retention_n=body.retention_n,
        schedule_enabled=body.schedule_enabled,
        schedule_interval_minutes=body.schedule_interval_minutes,
        quota_bytes=body.quota_bytes,
    )
    await session.commit()
    return await _settings_payload(service, current_user_id)


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


@router.post(
    "/{snapshot_id}/restore",
    response_model=RestoreResponse,
    summary="Restore the drive (or selected items) to a snapshot (in-place)",
)
async def restore_snapshot(
    snapshot_id: UUID,
    body: RestoreRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: SnapshotServiceDep,
) -> RestoreResponse:
    outcome = await service.restore(
        user_id=current_user_id,
        snapshot_id=snapshot_id,
        scope=body.scope,
        item_ids=body.item_ids,
        subtree_mode=body.subtree_mode,
    )
    if outcome is None:
        raise NotFoundError("Snapshot not found")
    await session.commit()
    return RestoreResponse(
        pre_restore_snapshot_id=outcome.pre_restore_snapshot_id,
        restored=outcome.restored,
        trashed=outcome.trashed,
    )
