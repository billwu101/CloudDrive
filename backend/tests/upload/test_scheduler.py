from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.upload.scheduler import UploadCleanupScheduler
from app.upload.session_service import UploadSessionService

pytestmark = pytest.mark.asyncio


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False

    async def commit(self) -> None:
        self.committed = True


def _make_scheduler(service: Any) -> tuple[UploadCleanupScheduler, list[_FakeSession]]:
    sessions: list[_FakeSession] = []

    @asynccontextmanager
    async def session_factory():  # type: ignore[no-untyped-def]
        session = _FakeSession()
        sessions.append(session)
        yield session

    scheduler = UploadCleanupScheduler(
        session_factory=session_factory,
        service_factory=lambda _session: service,
        interval_hours=24,
    )
    return scheduler, sessions


async def test_run_once_reclaims_and_commits() -> None:
    service = AsyncMock(spec=UploadSessionService)
    service.cleanup_expired.return_value = 3
    scheduler, sessions = _make_scheduler(service)

    removed = await scheduler.run_once()

    assert removed == 3
    service.cleanup_expired.assert_awaited_once()
    assert sessions[0].committed


async def test_run_once_swallows_failures_so_the_loop_survives() -> None:
    service = AsyncMock(spec=UploadSessionService)
    service.cleanup_expired.side_effect = RuntimeError("DB is down")
    scheduler, _ = _make_scheduler(service)

    # A broken pass must not propagate — the scheduler has to keep ticking.
    assert await scheduler.run_once() == 0


async def test_run_forever_stops_when_asked() -> None:
    service = AsyncMock(spec=UploadSessionService)
    service.cleanup_expired.return_value = 0
    scheduler, _ = _make_scheduler(service)
    stop = asyncio.Event()

    task = asyncio.create_task(scheduler.run_forever(stop))
    await asyncio.sleep(0)  # let the first pass run
    stop.set()
    await asyncio.wait_for(task, timeout=2)

    service.cleanup_expired.assert_awaited()
