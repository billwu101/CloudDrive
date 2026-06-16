from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.assistant.router import _assistant_service
from app.assistant.router import router as assistant_router
from app.assistant.schemas import AssistantChatResponse
from app.assistant.service import WorkflowService
from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token


def _make_app(service: WorkflowService, user_id: UUID) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppError)
    async def _err(request: Any, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {"code": str(exc.code), "message": exc.message, "details": exc.details}
            },
        )

    async def _fake_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_assistant_service] = lambda: service
    app.include_router(assistant_router)
    return app


@pytest.fixture()
def user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def headers(user_id: UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


async def test_chat_dispatches_to_agent_service(
    user_id: UUID,
    headers: dict[str, str],
) -> None:
    response = AssistantChatResponse(session_id=uuid4(), message="Hello from assistant")
    svc = AsyncMock(spec=WorkflowService)
    svc.chat.return_value = response
    app = _make_app(svc, user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/assistant/chat", json={"message": "list my files"}, headers=headers
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Hello from assistant"
    svc.chat.assert_awaited_once()


async def test_chat_requires_auth() -> None:
    svc = AsyncMock(spec=WorkflowService)
    app = _make_app(svc, uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/assistant/chat", json={"message": "hello"})

    assert resp.status_code in (401, 403)
