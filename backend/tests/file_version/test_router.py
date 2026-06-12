from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token
from app.drive.service import DriveService
from app.file_version.router import _drive_svc, _file_version_svc
from app.file_version.router import router as fv_router
from app.file_version.schemas import FileVersionResponse
from app.file_version.service import FileVersionService
from app.models.drive_item import DriveItem


def _fv_resp(file_id: UUID, version_no: int = 1) -> FileVersionResponse:
    return FileVersionResponse(
        id=uuid4(),
        file_id=file_id,
        version_no=version_no,
        size_bytes=1024,
        checksum_sha256=None,
        created_by=uuid4(),
        created_at=datetime.now(UTC),
    )


def _make_app(drive_svc: DriveService, fv_svc: FileVersionService) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": str(exc.code), "message": exc.message}},
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_drive_svc] = lambda: drive_svc
    app.dependency_overrides[_file_version_svc] = lambda: fv_svc
    app.include_router(fv_router)
    return app


async def test_list_versions_returns_list() -> None:
    uid = uuid4()
    file_id = uuid4()
    versions = [_fv_resp(file_id, 2), _fv_resp(file_id, 1)]
    drive_svc = AsyncMock(spec=DriveService)
    drive_svc.get_raw_item.return_value = AsyncMock(spec=DriveItem)
    fv_svc = AsyncMock(spec=FileVersionService)
    fv_svc.list_versions.return_value = versions
    app = _make_app(drive_svc, fv_svc)
    headers = {"Authorization": f"Bearer {create_access_token(uid)}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/drive/items/{file_id}/versions", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["version_no"] == 2


async def test_list_versions_requires_auth() -> None:
    drive_svc = AsyncMock(spec=DriveService)
    fv_svc = AsyncMock(spec=FileVersionService)
    app = _make_app(drive_svc, fv_svc)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        resp = await c.get(f"/drive/items/{uuid4()}/versions")
    assert resp.status_code in (401, 403)
