from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppError,
    FileTooLargeError,
    InvalidOperationError,
    NotFoundError,
    QuotaExceededError,
)
from app.core.security import create_access_token
from app.models.upload_session import UploadSession
from app.upload.router import _upload_session_service
from app.upload.router import router as upload_router
from app.upload.session_service import UploadSessionService, UploadSessionStatus
from tests.upload.test_router import _item_resp

pytestmark = pytest.mark.asyncio


def _session(user_id: UUID, *, status: str = "pending", total_chunks: int = 3) -> UploadSession:
    now = datetime.now(UTC)
    return UploadSession(
        id=uuid4(),
        user_id=user_id,
        parent_id=None,
        filename="movie.mp4",
        mime_type="video/mp4",
        total_size=20 * 1024 * 1024,
        chunk_size=8 * 1024 * 1024,
        total_chunks=total_chunks,
        status=status,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(days=7),
    )


def _make_app(service: UploadSessionService, user_id: UUID) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": str(exc.code), "message": exc.message},
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_upload_session_service] = lambda: service
    app.include_router(upload_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def _client(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ── POST /upload/sessions ────────────────────────────────────────────────────


async def test_create_session_returns_201_with_chunk_plan(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.create_session.return_value = UploadSessionStatus(
        session=_session(user_id), uploaded_chunks=[]
    )
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post(
            "/upload/sessions",
            headers=headers,
            json={"filename": "movie.mp4", "total_size": 20 * 1024 * 1024},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["chunk_size"] == 8 * 1024 * 1024
    assert body["total_chunks"] == 3
    assert body["uploaded_chunks"] == []


async def test_create_session_over_limit_returns_413(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.create_session.side_effect = FileTooLargeError()
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post(
            "/upload/sessions", headers=headers, json={"filename": "f", "total_size": 1}
        )

    assert resp.status_code == 413
    assert resp.json()["code"] == ErrorCode.FILE_TOO_LARGE


async def test_create_session_over_quota_returns_413(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.create_session.side_effect = QuotaExceededError()
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post(
            "/upload/sessions", headers=headers, json={"filename": "f", "total_size": 1}
        )

    assert resp.status_code == 413
    assert resp.json()["code"] == ErrorCode.QUOTA_EXCEEDED


async def test_create_session_requires_auth(user_id: UUID) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post("/upload/sessions", json={"filename": "f", "total_size": 1})
    assert resp.status_code == 401


# ── GET /upload/sessions/{id} ────────────────────────────────────────────────


async def test_get_session_reports_uploaded_chunks(user_id: UUID, headers: dict[str, str]) -> None:
    session = _session(user_id, status="uploading")
    svc = AsyncMock(spec=UploadSessionService)
    svc.get_session.return_value = UploadSessionStatus(session=session, uploaded_chunks=[0, 2])
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.get(f"/upload/sessions/{session.id}", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["uploaded_chunks"] == [0, 2]
    assert resp.json()["status"] == "uploading"


async def test_get_session_unknown_returns_404(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.get_session.side_effect = NotFoundError("Upload session not found")
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.get(f"/upload/sessions/{uuid4()}", headers=headers)

    assert resp.status_code == 404
    assert resp.json()["code"] == ErrorCode.NOT_FOUND


# ── PUT /upload/sessions/{id}/chunks/{index} ─────────────────────────────────


async def test_upload_chunk_returns_204_and_passes_index(
    user_id: UUID, headers: dict[str, str]
) -> None:
    session = _session(user_id)
    svc = AsyncMock(spec=UploadSessionService)
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.put(
            f"/upload/sessions/{session.id}/chunks/2", headers=headers, content=b"chunk-bytes"
        )

    assert resp.status_code == 204
    args = svc.upload_chunk.await_args
    assert args.args[1] == session.id
    assert args.args[2] == 2


async def test_upload_chunk_on_terminal_session_returns_400(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.upload_chunk.side_effect = InvalidOperationError("Upload session is already cancelled")
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.put(f"/upload/sessions/{uuid4()}/chunks/0", headers=headers, content=b"x")

    assert resp.status_code == 400
    assert resp.json()["code"] == ErrorCode.INVALID_OPERATION


async def test_upload_chunk_requires_auth(user_id: UUID) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.put(f"/upload/sessions/{uuid4()}/chunks/0", content=b"x")
    assert resp.status_code == 401


# ── POST /upload/sessions/{id}/complete ──────────────────────────────────────


async def test_complete_returns_201_with_the_created_item(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.complete_session.return_value = _item_resp(user_id, name="movie.mp4")
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post(f"/upload/sessions/{uuid4()}/complete", headers=headers)

    assert resp.status_code == 201
    assert resp.json()["name"] == "movie.mp4"


async def test_complete_with_missing_chunks_returns_400(
    user_id: UUID, headers: dict[str, str]
) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.complete_session.side_effect = InvalidOperationError(
        "Upload is incomplete: 1 chunk(s) missing"
    )
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.post(f"/upload/sessions/{uuid4()}/complete", headers=headers)

    assert resp.status_code == 400
    assert resp.json()["code"] == ErrorCode.INVALID_OPERATION


# ── DELETE /upload/sessions/{id} ─────────────────────────────────────────────


async def test_cancel_returns_204(user_id: UUID, headers: dict[str, str]) -> None:
    session_id = uuid4()
    svc = AsyncMock(spec=UploadSessionService)
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.delete(f"/upload/sessions/{session_id}", headers=headers)

    assert resp.status_code == 204
    svc.cancel_session.assert_awaited_once_with(user_id, session_id)


async def test_cancel_unknown_returns_404(user_id: UUID, headers: dict[str, str]) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    svc.cancel_session.side_effect = NotFoundError("Upload session not found")
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.delete(f"/upload/sessions/{uuid4()}", headers=headers)

    assert resp.status_code == 404


async def test_cancel_requires_auth(user_id: UUID) -> None:
    svc = AsyncMock(spec=UploadSessionService)
    async with await _client(_make_app(svc, user_id)) as c:
        resp = await c.delete(f"/upload/sessions/{uuid4()}")
    assert resp.status_code == 401
