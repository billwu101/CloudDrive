from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.activity_log.actions import ActivityAction
from app.activity_log.repository import AbstractActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.models.activity_log import ActivityLog


def _make_log(actor_id: UUID, item_id: UUID | None = None, action: str = "create") -> ActivityLog:
    return ActivityLog(
        id=uuid4(),
        actor_id=actor_id,
        item_id=item_id,
        action=action,
        log_metadata={},
        ip_address=None,
        user_agent=None,
        created_at=datetime.now(UTC),
    )


class MockActivityLogRepo(AbstractActivityLogRepository):
    def __init__(self) -> None:
        self.logs: list[ActivityLog] = []
        self.fail_next: bool = False

    async def create(
        self,
        *,
        actor_id: UUID,
        item_id: UUID | None,
        action: str,
        metadata: dict[str, Any],
        ip_address: str | None,
        user_agent: str | None,
    ) -> ActivityLog:
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("Simulated log failure")
        log = ActivityLog(
            id=uuid4(),
            actor_id=actor_id,
            item_id=item_id,
            action=action,
            log_metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
        self.logs.append(log)
        return log

    async def list_by_actor(self, actor_id: UUID, *, limit: int = 50) -> list[ActivityLog]:
        return [entry for entry in self.logs if entry.actor_id == actor_id][:limit]

    async def list_by_item(self, item_id: UUID, *, limit: int = 50) -> list[ActivityLog]:
        return [entry for entry in self.logs if entry.item_id == item_id][:limit]

    async def get_recent_item_ids(
        self,
        actor_id: UUID,
        *,
        limit: int = 20,
        exclude_item_ids: set[UUID] | None = None,
    ) -> list[UUID]:
        seen: dict[UUID, datetime] = {}
        for log in self.logs:
            if (
                log.actor_id == actor_id
                and log.item_id is not None
                and (log.item_id not in seen or log.created_at > seen[log.item_id])
            ):
                seen[log.item_id] = log.created_at
        excluded = exclude_item_ids or set()
        sorted_ids = sorted(
            (iid for iid in seen if iid not in excluded),
            key=lambda iid: seen[iid],
            reverse=True,
        )
        return sorted_ids[:limit]


async def test_log_writes_entry() -> None:
    repo = MockActivityLogRepo()
    svc = ActivityLogService(repo)
    actor = uuid4()
    item = uuid4()
    result = await svc.log(actor_id=actor, action=ActivityAction.CREATE, item_id=item)
    assert result is not None
    assert len(repo.logs) == 1
    assert repo.logs[0].action == ActivityAction.CREATE


async def test_log_with_metadata() -> None:
    repo = MockActivityLogRepo()
    svc = ActivityLogService(repo)
    actor = uuid4()
    result = await svc.log(
        actor_id=actor,
        action=ActivityAction.RENAME,
        metadata={"old_name": "foo.txt", "new_name": "bar.txt"},
    )
    assert result is not None
    assert repo.logs[0].log_metadata["old_name"] == "foo.txt"


async def test_log_item_id_can_be_null() -> None:
    repo = MockActivityLogRepo()
    svc = ActivityLogService(repo)
    result = await svc.log(actor_id=uuid4(), action=ActivityAction.DOWNLOAD)
    assert result is not None
    assert repo.logs[0].item_id is None


async def test_log_failure_does_not_raise() -> None:
    repo = MockActivityLogRepo()
    repo.fail_next = True
    svc = ActivityLogService(repo)
    result = await svc.log(actor_id=uuid4(), action=ActivityAction.CREATE)
    assert result is None
    assert len(repo.logs) == 0


async def test_get_recent_item_ids_returns_sorted() -> None:
    repo = MockActivityLogRepo()
    actor = uuid4()
    item1, item2, item3 = uuid4(), uuid4(), uuid4()
    svc = ActivityLogService(repo)
    await svc.log(actor_id=actor, action=ActivityAction.CREATE, item_id=item1)
    await svc.log(actor_id=actor, action=ActivityAction.PREVIEW, item_id=item2)
    await svc.log(actor_id=actor, action=ActivityAction.DOWNLOAD, item_id=item3)
    ids = await svc.get_recent_item_ids(actor)
    assert ids == [item3, item2, item1]


async def test_get_recent_excludes_specified_ids() -> None:
    repo = MockActivityLogRepo()
    actor = uuid4()
    item1, item2 = uuid4(), uuid4()
    svc = ActivityLogService(repo)
    await svc.log(actor_id=actor, action=ActivityAction.CREATE, item_id=item1)
    await svc.log(actor_id=actor, action=ActivityAction.CREATE, item_id=item2)
    ids = await svc.get_recent_item_ids(actor, exclude_item_ids={item2})
    assert item2 not in ids
    assert item1 in ids
