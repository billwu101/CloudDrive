from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.snapshot.service import GcOutcome, SnapshotService

logger = logging.getLogger("app.snapshot.scheduler")

# A factory yielding a DB session as an async context manager.
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
# Builds a SnapshotService (with storage, for GC) bound to a given session.
ServiceFactory = Callable[[AsyncSession], SnapshotService]
# Returns the ids of every user, given a session.
UserIdsProvider = Callable[[AsyncSession], Awaitable[list[UUID]]]


class SnapshotScheduler:
    """In-process periodic runner for Time Machine.

    Each tick it (1) asks every user's ``run_scheduled_snapshot`` to create a
    snapshot if one is due, and (2) runs blob GC at its own slower cadence. The
    underlying service methods are idempotent/guarded (interval checks, grace
    window), so an occasional double-fire is harmless — but this is a
    single-process runner. For multi-worker deployments, disable it and drive the
    same ``SnapshotService`` methods from an external scheduler instead.
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        service_factory: ServiceFactory,
        user_ids_provider: UserIdsProvider,
        tick_seconds: int = 300,
        gc_interval_minutes: int = 360,
        gc_grace_minutes: int = 60,
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._user_ids_provider = user_ids_provider
        self._tick_seconds = tick_seconds
        self._gc_interval_minutes = gc_interval_minutes
        self._gc_grace_minutes = gc_grace_minutes
        self._last_gc: datetime | None = None

    async def run_once(self, *, now: datetime | None = None) -> tuple[int, GcOutcome | None]:
        """One scheduler pass. Returns (scheduled snapshots created, GC outcome
        or None if GC wasn't due this pass)."""
        now = now or datetime.now(UTC)
        created = await self._run_scheduled(now)
        gc: GcOutcome | None = None
        if self._due_for_gc(now):
            gc = await self._run_gc(now)
            self._last_gc = now
        return created, gc

    async def run_forever(self, stop: asyncio.Event) -> None:
        """Loop until ``stop`` is set, sleeping ``tick_seconds`` between passes.
        Any pass failure is logged and swallowed so the loop survives."""
        logger.info("snapshot scheduler started (tick=%ss)", self._tick_seconds)
        while not stop.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("snapshot scheduler tick failed")
            # Sleep until the next tick, or wake early when asked to stop.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._tick_seconds)
        logger.info("snapshot scheduler stopped")

    async def _run_scheduled(self, now: datetime) -> int:
        async with self._session_factory() as session:
            user_ids = await self._user_ids_provider(session)
        created = 0
        for user_id in user_ids:
            try:
                async with self._session_factory() as session:
                    service = self._service_factory(session)
                    snapshot = await service.run_scheduled_snapshot(user_id=user_id, now=now)
                    if snapshot is not None:
                        created += 1
                    await session.commit()
            except Exception:
                logger.exception("scheduled snapshot failed for user %s", user_id)
        return created

    def _due_for_gc(self, now: datetime) -> bool:
        if self._last_gc is None:
            return True
        return (now - self._last_gc).total_seconds() >= self._gc_interval_minutes * 60

    async def _run_gc(self, now: datetime) -> GcOutcome | None:
        try:
            async with self._session_factory() as session:
                service = self._service_factory(session)
                outcome = await service.collect_garbage(
                    grace_minutes=self._gc_grace_minutes, now=now
                )
                await session.commit()
                logger.info(
                    "blob GC: deleted=%d freed=%d skipped_recent=%d",
                    outcome.deleted,
                    outcome.freed_bytes,
                    outcome.skipped_recent,
                )
                return outcome
        except Exception:
            logger.exception("blob GC failed")
            return None


def build_default_scheduler() -> SnapshotScheduler:
    """Wire a scheduler against the real DB session factory and storage."""
    from app.activity_log.repository import SQLActivityLogRepository
    from app.activity_log.service import ActivityLogService
    from app.core.config import get_settings
    from app.db.base import AsyncSessionLocal
    from app.snapshot.repository import SQLSnapshotRepository
    from app.storage.factory import get_storage_provider
    from app.users.repository import SQLUserRepository

    settings = get_settings()
    storage = get_storage_provider(settings)

    def service_factory(session: AsyncSession) -> SnapshotService:
        return SnapshotService(
            repo=SQLSnapshotRepository(session),
            activity=ActivityLogService(SQLActivityLogRepository(session)),
            storage=storage,
        )

    async def user_ids_provider(session: AsyncSession) -> list[UUID]:
        return await SQLUserRepository(session).list_all_ids()

    return SnapshotScheduler(
        session_factory=AsyncSessionLocal,
        service_factory=service_factory,
        user_ids_provider=user_ids_provider,
        tick_seconds=settings.snapshot_scheduler_tick_seconds,
        gc_interval_minutes=settings.snapshot_gc_interval_minutes,
        gc_grace_minutes=settings.snapshot_gc_grace_minutes,
    )
