from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.upload.session_service import UploadSessionService

logger = logging.getLogger("app.upload.scheduler")

# A factory yielding a DB session as an async context manager.
SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]
# Builds an UploadSessionService bound to a given session.
ServiceFactory = Callable[[AsyncSession], UploadSessionService]


class UploadCleanupScheduler:
    """In-process periodic reclaim of expired upload sessions.

    Unfinished sessions hold chunk blobs that nothing else will ever collect —
    content GC deliberately ignores the upload prefix, since those blobs belong
    to an upload in progress rather than to a drive item. This is a
    single-process runner: for multi-worker deployments disable it and call
    ``cleanup_expired`` from an external cron instead, so workers don't race.
    """

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        service_factory: ServiceFactory,
        interval_hours: int = 24,
    ) -> None:
        self._session_factory = session_factory
        self._service_factory = service_factory
        self._interval_seconds = interval_hours * 3600
        self._last_run: datetime | None = None

    async def run_once(self, *, now: datetime | None = None) -> int:
        """One pass. Returns the number of sessions reclaimed."""
        now = now or datetime.now(UTC)
        try:
            async with self._session_factory() as session:
                service = self._service_factory(session)
                removed = await service.cleanup_expired()
                await session.commit()
        except Exception:
            logger.exception("upload session cleanup failed")
            return 0
        self._last_run = now
        if removed:
            logger.info("upload session cleanup: reclaimed %d expired session(s)", removed)
        return removed

    async def run_forever(self, stop: asyncio.Event) -> None:
        """Loop until ``stop`` is set. A failed pass is logged, never fatal."""
        logger.info("upload cleanup scheduler started (interval=%ss)", self._interval_seconds)
        while not stop.is_set():
            await self.run_once()
            # Sleep until the next pass, or wake early when asked to stop.
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop.wait(), timeout=self._interval_seconds)
        logger.info("upload cleanup scheduler stopped")


def build_default_scheduler() -> UploadCleanupScheduler:
    """Wire a cleanup scheduler against the real DB session factory and storage."""
    from app.core.config import get_settings
    from app.db.base import AsyncSessionLocal
    from app.drive.repository import SQLDriveItemRepository
    from app.file_version.repository import SQLFileVersionRepository
    from app.permission.repository import SQLShareRepository
    from app.permission.service import PermissionService
    from app.storage.factory import get_storage_provider
    from app.upload.session_repository import SQLUploadSessionRepository
    from app.users.repository import SQLUserRepository
    from app.users.service import QuotaService

    settings = get_settings()
    storage = get_storage_provider(settings)

    def service_factory(session: AsyncSession) -> UploadSessionService:
        return UploadSessionService(
            session_repo=SQLUploadSessionRepository(session),
            item_repo=SQLDriveItemRepository(session),
            version_repo=SQLFileVersionRepository(session),
            storage=storage,
            permission_svc=PermissionService(
                share_repo=SQLShareRepository(session),
                item_repo=SQLDriveItemRepository(session),
            ),
            quota_svc=QuotaService(repo=SQLUserRepository(session)),
            chunk_size=settings.upload_chunk_size_bytes,
            max_file_size=settings.max_chunked_upload_size_bytes,
            retention_days=settings.upload_session_retention_days,
        )

    return UploadCleanupScheduler(
        session_factory=AsyncSessionLocal,
        service_factory=service_factory,
        interval_hours=settings.upload_cleanup_interval_hours,
    )
