from __future__ import annotations

from collections.abc import AsyncGenerator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.assistant.repository import AbstractAssistantSessionRepository
from app.assistant.router import _assistant_service, _assistant_session_repo
from app.assistant.router import router as assistant_router
from app.assistant.schemas import AssistantChatResponse
from app.assistant.service import WorkflowService
from app.core.dependencies import get_db
from app.core.exceptions import AppError
from app.core.security import create_access_token


def _make_app(
    service: WorkflowService,
    user_id: UUID,
    session_repo: AbstractAssistantSessionRepository | None = None,
) -> FastAPI:
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

    repo = session_repo or AsyncMock(spec=AbstractAssistantSessionRepository)
    app.dependency_overrides[get_db] = _fake_db
    app.dependency_overrides[_assistant_service] = lambda: service
    app.dependency_overrides[_assistant_session_repo] = lambda: repo
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


async def test_chat_persists_user_and_assistant_messages(
    user_id: UUID,
    headers: dict[str, str],
) -> None:
    session_id = uuid4()
    response = AssistantChatResponse(session_id=session_id, message="done")
    svc = AsyncMock(spec=WorkflowService)
    svc.chat.return_value = response
    repo = AsyncMock(spec=AbstractAssistantSessionRepository)
    app = _make_app(svc, user_id, session_repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/assistant/chat", json={"message": "make a folder"}, headers=headers
        )

    assert resp.status_code == 200
    repo.ensure_session.assert_awaited_once()
    assert repo.ensure_session.await_args.kwargs["session_id"] == session_id
    roles = [call.kwargs["role"] for call in repo.add_message.await_args_list]
    assert roles == ["user", "assistant"]


async def test_list_sessions_returns_repo_rows(
    user_id: UUID,
    headers: dict[str, str],
) -> None:
    now = "2026-06-17T00:00:00Z"
    repo = AsyncMock(spec=AbstractAssistantSessionRepository)
    repo.list_sessions.return_value = [
        SimpleNamespace(id=uuid4(), title="make a folder", created_at=now, updated_at=now)
    ]
    app = _make_app(AsyncMock(spec=WorkflowService), user_id, session_repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/assistant/sessions", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["title"] == "make a folder"
    repo.list_sessions.assert_awaited_once_with(user_id=user_id)


async def test_list_session_messages_returns_history(
    user_id: UUID,
    headers: dict[str, str],
) -> None:
    session_id = uuid4()
    now = "2026-06-17T00:00:00Z"
    repo = AsyncMock(spec=AbstractAssistantSessionRepository)
    repo.list_messages.return_value = [
        SimpleNamespace(id=uuid4(), role="user", content="hi", tool_calls=[], created_at=now),
        SimpleNamespace(id=uuid4(), role="assistant", content="hey", tool_calls=[], created_at=now),
    ]
    app = _make_app(AsyncMock(spec=WorkflowService), user_id, session_repo=repo)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/assistant/sessions/{session_id}/messages", headers=headers)

    assert resp.status_code == 200
    body = resp.json()
    assert [m["role"] for m in body] == ["user", "assistant"]
    repo.list_messages.assert_awaited_once_with(user_id=user_id, session_id=session_id)


async def test_chat_requires_auth() -> None:
    svc = AsyncMock(spec=WorkflowService)
    app = _make_app(svc, uuid4())

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/assistant/chat", json={"message": "hello"})

    assert resp.status_code in (401, 403)
