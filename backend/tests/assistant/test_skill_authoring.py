from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.assistant.repository import AbstractAssistantSkillRepository
from app.assistant.skills.authoring import AssistantSkillService
from app.drive.repository import AbstractDriveItemRepository, AbstractUserItemPreferenceRepository
from app.drive.schemas import DriveItemSortField, ItemType
from app.drive.service import DriveService
from app.models.assistant_skill import AssistantSkill
from app.models.drive_item import DriveItem
from app.models.user_item_preference import UserItemPreference
from app.schemas.common import SortOrder


class MemAssistantSkillRepo(AbstractAssistantSkillRepository):
    def __init__(self) -> None:
        self._skills: dict[UUID, AssistantSkill] = {}

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = self._skills.get(skill_id)
        if skill is None or skill.user_id != user_id:
            return None
        return skill

    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None:
        return next(
            (
                skill
                for skill in self._skills.values()
                if skill.user_id == user_id and skill.name == name
            ),
            None,
        )

    async def list_by_status(
        self,
        *,
        user_id: UUID,
        status: str | None = None,
    ) -> list[AssistantSkill]:
        return [
            skill
            for skill in self._skills.values()
            if skill.user_id == user_id and (status is None or skill.status == status)
        ]

    async def create_or_replace_pending(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill:
        now = datetime.now(UTC)
        skill = await self.get_by_name(user_id=user_id, name=name)
        if skill is None:
            skill = AssistantSkill(
                id=uuid4(),
                user_id=user_id,
                name=name,
                description=description,
                manifest=manifest,
                code=code,
                status="pending",
                created_at=now,
                updated_at=now,
            )
            self._skills[skill.id] = skill
        else:
            skill.description = description
            skill.manifest = manifest
            skill.code = code
            skill.status = "pending"
            skill.updated_at = now
        return skill

    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = await self.get_by_id(user_id=user_id, skill_id=skill_id)
        if skill is None:
            return None
        skill.status = "installed"
        skill.updated_at = datetime.now(UTC)
        return skill


def _item(*, owner_id: UUID, name: str = "report.txt") -> DriveItem:
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=None,
        item_type=ItemType.FILE,
        name=name,
        mime_type="text/plain",
        extension="txt",
        size_bytes=1024,
        storage_key=None,
        checksum_sha256=None,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


class MemDriveItemRepo(AbstractDriveItemRepository):
    def __init__(self, items: list[DriveItem]) -> None:
        self._items = {item.id: item for item in items}

    async def get_by_id(self, item_id: UUID) -> DriveItem | None:
        return self._items.get(item_id)

    async def list_children(
        self,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        sort_by: DriveItemSortField,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[DriveItem], int]:
        return [], 0

    async def create(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID | None,
        item_type: str,
        name: str,
        created_by: UUID,
    ) -> DriveItem:
        raise NotImplementedError

    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem:
        raise NotImplementedError

    async def update_parent(
        self,
        item_id: UUID,
        parent_id: UUID | None,
        updated_by: UUID,
    ) -> DriveItem:
        raise NotImplementedError

    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        return False


class MemPrefRepo(AbstractUserItemPreferenceRepository):
    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None:
        return None

    async def upsert_preference(
        self,
        user_id: UUID,
        item_id: UUID,
        *,
        is_starred: bool,
    ) -> UserItemPreference:
        raise NotImplementedError

    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]:
        return set()


def _svc(
    repo: MemAssistantSkillRepo,
    items: list[DriveItem] | None = None,
) -> AssistantSkillService:
    return AssistantSkillService(
        repo=repo,
        drive_service=DriveService(
            item_repo=MemDriveItemRepo(items or []),
            pref_repo=MemPrefRepo(),
        ),
    )


async def test_authoring_message_creates_pending_context_menu_manifest() -> None:
    user_id = uuid4()
    repo = MemAssistantSkillRepo()
    service = _svc(repo)

    result = await service.handle_authoring_message(
        user_id=user_id,
        message="新增一個右鍵 inspect details 功能",
    )

    assert result is not None
    assert result.skill_proposal is not None
    assert result.skill_proposal.status == "pending"
    action = result.skill_proposal.manifest["ui"]["context_menu"][0]
    assert action["label"] == "Inspect details"
    assert action["item_types"] == ["FILE", "FOLDER"]


async def test_authoring_message_does_not_reinstall_existing_skill() -> None:
    user_id = uuid4()
    repo = MemAssistantSkillRepo()
    service = _svc(repo)

    first = await service.handle_authoring_message(
        user_id=user_id,
        message="create a right click inspect details action",
    )
    assert first is not None
    assert first.skill_proposal is not None
    await service.approve_skill(user_id=user_id, skill_id=first.skill_proposal.id)

    second = await service.handle_authoring_message(
        user_id=user_id,
        message="create a right click inspect details action",
    )

    assert second is not None
    assert second.skill_proposal is None
    assert "already installed" in second.message


async def test_execute_installed_inspect_skill_returns_item_metadata() -> None:
    user_id = uuid4()
    item = _item(owner_id=user_id)
    repo = MemAssistantSkillRepo()
    service = _svc(repo, [item])

    proposal = await service.handle_authoring_message(
        user_id=user_id,
        message="create a right click inspect details action",
    )
    assert proposal is not None
    assert proposal.skill_proposal is not None
    installed = await service.approve_skill(user_id=user_id, skill_id=proposal.skill_proposal.id)

    result = await service.execute_skill(
        user_id=user_id,
        skill_id=installed.id,
        item_id=item.id,
    )

    assert result.message == "Details for report.txt"
    assert result.output["name"] == "report.txt"
    assert result.output["size_bytes"] == 1024
