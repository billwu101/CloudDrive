from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.snapshot.scheduler import SnapshotScheduler
from app.snapshot.service import GcOutcome, SnapshotService
from app.storage.base import StoredObject
from tests.snapshot.test_service import MemSnapshotRepo, _FakeStorage, _item


class _FakeSession:
    # The scheduler only calls commit() on the session; the injected factories
    # ignore it and talk to the in-memory repo directly.
    async def commit(self) -> None:
        return None


@asynccontextmanager
async def _null_session() -> AsyncIterator[AsyncSession]:
    yield cast(AsyncSession, _FakeSession())


def _make_scheduler(
    repo: MemSnapshotRepo,
    user_ids: list[UUID],
    *,
    storage: _FakeStorage | None = None,
    gc_interval_minutes: int = 360,
) -> SnapshotScheduler:
    def service_factory(_session: object) -> SnapshotService:
        return SnapshotService(repo=repo, storage=storage)

    async def user_ids_provider(_session: object) -> list[UUID]:
        return user_ids

    return SnapshotScheduler(
        session_factory=_null_session,
        service_factory=service_factory,
        user_ids_provider=user_ids_provider,
        tick_seconds=1,
        gc_interval_minutes=gc_interval_minutes,
        gc_grace_minutes=60,
    )


async def test_run_once_creates_due_snapshots_for_each_user() -> None:
    u1, u2 = uuid4(), uuid4()
    repo = MemSnapshotRepo([_item(u1), _item(u2)])
    storage = _FakeStorage([])
    scheduler = _make_scheduler(repo, [u1, u2], storage=storage)

    created, gc = await scheduler.run_once()

    assert created == 2  # both users had no prior snapshot and a non-empty drive
    assert gc is not None  # GC runs on the first pass
    # A second immediate pass: interval not elapsed, GC not due again.
    created2, gc2 = await scheduler.run_once()
    assert created2 == 0
    assert gc2 is None


async def test_run_once_runs_gc_and_reclaims_orphans() -> None:
    user = uuid4()
    f = _item(user, name="a.txt")
    f.storage_key = "blob-a"
    repo = MemSnapshotRepo([f])
    now = datetime.now(UTC)
    storage = _FakeStorage(
        [
            StoredObject(key="blob-a", size=100, modified_at=now.timestamp()),
            StoredObject(
                key="orphan", size=200, modified_at=(now - timedelta(hours=2)).timestamp()
            ),
        ]
    )
    scheduler = _make_scheduler(repo, [user], storage=storage)

    _created, gc = await scheduler.run_once(now=now)

    assert gc is not None
    assert gc.deleted == 1
    assert storage.deleted == ["orphan"]


async def test_run_once_gc_due_again_after_interval() -> None:
    user = uuid4()
    repo = MemSnapshotRepo([_item(user)])
    scheduler = _make_scheduler(repo, [user], storage=_FakeStorage([]), gc_interval_minutes=60)

    t0 = datetime.now(UTC)
    _, gc0 = await scheduler.run_once(now=t0)
    assert gc0 is not None  # first pass

    _, gc1 = await scheduler.run_once(now=t0 + timedelta(minutes=30))
    assert gc1 is None  # within interval

    _, gc2 = await scheduler.run_once(now=t0 + timedelta(minutes=61))
    assert gc2 is not None  # interval elapsed


async def test_run_forever_stops_on_event() -> None:
    user = uuid4()
    repo = MemSnapshotRepo([_item(user)])

    class _Counting(SnapshotScheduler):
        ticks = 0

        async def run_once(self, *, now: datetime | None = None) -> tuple[int, GcOutcome | None]:
            type(self).ticks += 1
            return await super().run_once(now=now)

    def service_factory(_session: object) -> SnapshotService:
        return SnapshotService(repo=repo, storage=_FakeStorage([]))

    async def user_ids_provider(_session: object) -> list[UUID]:
        return [user]

    scheduler = _Counting(
        session_factory=_null_session,
        service_factory=service_factory,
        user_ids_provider=user_ids_provider,
        tick_seconds=0.01,  # type: ignore[arg-type]
    )
    stop = asyncio.Event()
    task = asyncio.create_task(scheduler.run_forever(stop))
    await asyncio.sleep(0.03)
    stop.set()
    await asyncio.wait_for(task, timeout=1)

    assert _Counting.ticks >= 1  # looped at least once and then exited cleanly
