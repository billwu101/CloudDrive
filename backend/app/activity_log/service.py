from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.activity_log.repository import AbstractActivityLogRepository
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)


class ActivityLogService:
    """Writes activity log entries.

    Log failures are swallowed after being logged — they must never break the
    caller's primary flow.
    """

    def __init__(self, repo: AbstractActivityLogRepository) -> None:
        self._repo = repo

    async def log(
        self,
        *,
        actor_id: UUID,
        action: str,
        item_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ActivityLog | None:
        try:
            return await self._repo.create(
                actor_id=actor_id,
                item_id=item_id,
                action=action,
                metadata=metadata or {},
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception:
            logger.exception(
                "Failed to write activity log: actor=%s action=%s item=%s",
                actor_id,
                action,
                item_id,
            )
            return None

    async def get_recent_item_ids(
        self,
        actor_id: UUID,
        *,
        limit: int = 20,
        exclude_item_ids: set[UUID] | None = None,
    ) -> list[UUID]:
        return await self._repo.get_recent_item_ids(
            actor_id,
            limit=limit,
            exclude_item_ids=exclude_item_ids,
        )
