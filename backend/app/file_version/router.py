from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.core.dependencies import CurrentUserId, DbSession
from app.drive.repository import SQLDriveItemRepository, SQLUserItemPreferenceRepository
from app.drive.service import DriveService
from app.file_version.repository import SQLFileVersionRepository
from app.file_version.schemas import FileVersionResponse
from app.file_version.service import FileVersionService
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService

router = APIRouter(prefix="/drive", tags=["file-versions"])


def _permission_svc(session: DbSession) -> PermissionService:
    return PermissionService(
        share_repo=SQLShareRepository(session),
        item_repo=SQLDriveItemRepository(session),
    )


def _file_version_svc(
    session: DbSession,
    permission_svc: Annotated[PermissionService, Depends(_permission_svc)],
) -> FileVersionService:
    return FileVersionService(
        version_repo=SQLFileVersionRepository(session),
        permission_svc=permission_svc,
    )


def _drive_svc(session: DbSession) -> DriveService:
    return DriveService(
        item_repo=SQLDriveItemRepository(session),
        pref_repo=SQLUserItemPreferenceRepository(session),
        activity_svc=ActivityLogService(SQLActivityLogRepository(session)),
    )


FileVersionServiceDep = Annotated[FileVersionService, Depends(_file_version_svc)]
DriveSvcDep = Annotated[DriveService, Depends(_drive_svc)]


@router.get(
    "/items/{item_id}/versions",
    response_model=list[FileVersionResponse],
    summary="List all versions of a file",
)
async def list_versions(
    item_id: UUID,
    current_user_id: CurrentUserId,
    drive_svc: DriveSvcDep,
    version_svc: FileVersionServiceDep,
) -> list[FileVersionResponse]:
    item = await drive_svc.get_raw_item(current_user_id, item_id)
    return await version_svc.list_versions(current_user_id, item)
