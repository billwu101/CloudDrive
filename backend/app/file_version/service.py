from __future__ import annotations

from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.schemas import ItemType
from app.file_version.repository import AbstractFileVersionRepository
from app.file_version.schemas import FileVersionResponse
from app.models.drive_item import DriveItem
from app.models.file_version import FileVersion
from app.permission.service import PermissionService


class FileVersionService:
    def __init__(
        self,
        version_repo: AbstractFileVersionRepository,
        permission_svc: PermissionService,
    ) -> None:
        self._repo = version_repo
        self._perm = permission_svc

    async def create_version(
        self,
        user_id: UUID,
        item: DriveItem,
        storage_key: str,
        size_bytes: int,
        checksum_sha256: str | None = None,
    ) -> FileVersion:
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Only files can have versions")
        await self._perm.assert_can_edit(user_id, item)
        next_no = await self._repo.get_max_version_no(item.id) + 1
        return await self._repo.create(
            file_id=item.id,
            version_no=next_no,
            storage_key=storage_key,
            size_bytes=size_bytes,
            checksum_sha256=checksum_sha256,
            created_by=user_id,
        )

    async def list_versions(
        self,
        user_id: UUID,
        item: DriveItem,
    ) -> list[FileVersionResponse]:
        if item.item_type != ItemType.FILE:
            raise AppError(ErrorCode.INVALID_OPERATION, "Only files have versions")
        await self._perm.assert_can_view(user_id, item)
        versions = await self._repo.list_by_file(item.id)
        return [FileVersionResponse.model_validate(v) for v in versions]
