from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.assistant.repository import AbstractAssistantSkillRepository
from app.assistant.schemas import AssistantSkillExecuteResponse, AssistantSkillResponse
from app.assistant.skills.manifest import validate_manifest
from app.assistant.subagent import CodegenSubAgent
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError
from app.drive.service import DriveService
from app.models.assistant_skill import AssistantSkill
from app.schemas.common import DriveItemResponse

INSPECT_DETAILS_SKILL_NAME = "inspect_item_details"
INSPECT_DETAILS_DESCRIPTION = "Show details for a selected drive item."
_PENDING = "pending"
_INSTALLED = "installed"

# Verbs that signal "author a brand-new capability" rather than a normal file op.
_GENERATION_VERBS = (
    "做一個",
    "做個",
    "製作",
    "生成",
    "新增功能",
    "建立一個功能",
    "幫我做",
    "make",
    "create",
    "build",
    "generate",
    "author",
    "add a",
)
# A skill-ish noun or a known file-operation keyword the built-ins don't cover.
_GENERATION_TARGETS = (
    "功能",
    "技能",
    "skill",
    "function",
    "feature",
    "解壓",
    "解壓縮",
    "壓縮",
    "7zip",
    "7-zip",
    "decompress",
    "compress",
    "extract",
    "convert",
    "轉換",
    "縮圖",
    "thumbnail",
)


@dataclass(frozen=True)
class AssistantAuthoringResult:
    message: str
    skill_proposal: AssistantSkillResponse | None = None


def _inspect_details_manifest() -> dict[str, Any]:
    return {
        "name": INSPECT_DETAILS_SKILL_NAME,
        "description": INSPECT_DETAILS_DESCRIPTION,
        "version": "1.0.0",
        "ui": {
            "context_menu": [
                {
                    "label": "Inspect details",
                    "handler": INSPECT_DETAILS_SKILL_NAME,
                    "item_types": ["FILE", "FOLDER"],
                }
            ]
        },
    }


def _inspect_details_code() -> str:
    return "\n".join(
        [
            "handler: inspect_item_details",
            "permission: read",
            "input: { item_id: uuid }",
            "output: selected item's metadata for a right-click details panel",
        ]
    )


def _looks_like_context_menu_skill_request(message: str) -> bool:
    lowered = message.lower()
    menu_requested = any(
        phrase in lowered
        for phrase in (
            "right click",
            "right-click",
            "context menu",
            "右鍵",
            "選單",
        )
    )
    details_requested = any(
        phrase in lowered
        for phrase in (
            "inspect",
            "detail",
            "details",
            "metadata",
            "建立",
            "新增",
            "新功能",
            "查看",
        )
    )
    return menu_requested and details_requested


def _looks_like_skill_generation_request(message: str) -> bool:
    """Detect "author a new skill" intent (e.g. a 7zip extractor) distinct from
    a normal built-in file operation like creating a folder."""

    lowered = message.lower()
    has_verb = any(verb.lower() in lowered for verb in _GENERATION_VERBS)
    has_target = any(target.lower() in lowered for target in _GENERATION_TARGETS)
    return has_verb and has_target


def _skill_response(skill: AssistantSkill) -> AssistantSkillResponse:
    return AssistantSkillResponse(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        manifest=skill.manifest,
        code=skill.code,
        status=skill.status,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


def _item_output(item: DriveItemResponse) -> dict[str, Any]:
    return {
        "name": item.name,
        "item_type": item.item_type,
        "size_bytes": item.size_bytes,
        "mime_type": item.mime_type,
        "extension": item.extension,
        "is_starred": item.is_starred,
        "is_deleted": item.is_deleted,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


class AssistantSkillService:
    def __init__(
        self,
        *,
        repo: AbstractAssistantSkillRepository,
        drive_service: DriveService,
        codegen: CodegenSubAgent | None = None,
    ) -> None:
        self._repo = repo
        self._drive = drive_service
        self._codegen = codegen

    async def handle_authoring_message(
        self,
        *,
        user_id: UUID,
        message: str,
    ) -> AssistantAuthoringResult | None:
        if _looks_like_context_menu_skill_request(message):
            return await self._propose_inspect_details(user_id=user_id)
        if self._codegen is not None and _looks_like_skill_generation_request(message):
            return await self._generate_skill(user_id=user_id, message=message)
        return None

    async def _propose_inspect_details(self, *, user_id: UUID) -> AssistantAuthoringResult:
        installed = await self._repo.get_by_name(
            user_id=user_id,
            name=INSPECT_DETAILS_SKILL_NAME,
        )
        if installed is not None and installed.status == _INSTALLED:
            return AssistantAuthoringResult(
                message="Inspect details is already installed in the right-click menu."
            )

        # Validate before persisting: a malformed manifest never becomes a proposal.
        manifest = validate_manifest(_inspect_details_manifest()).model_dump(mode="json")
        skill = await self._repo.create_or_replace_pending(
            user_id=user_id,
            name=INSPECT_DETAILS_SKILL_NAME,
            description=INSPECT_DETAILS_DESCRIPTION,
            manifest=manifest,
            code=_inspect_details_code(),
        )
        return AssistantAuthoringResult(
            message=(
                "I drafted a right-click menu skill named Inspect details. "
                "Review and approve it to install the manifest."
            ),
            skill_proposal=_skill_response(skill),
        )

    async def _generate_skill(
        self,
        *,
        user_id: UUID,
        message: str,
    ) -> AssistantAuthoringResult:
        assert self._codegen is not None
        result = await self._codegen.author(request=message)
        if not result.ok or result.manifest is None:
            detail = f" ({'; '.join(result.problems)})" if result.problems else ""
            return AssistantAuthoringResult(message=result.reply + detail)

        # Persist as a pending proposal only — generation never auto-installs or
        # auto-executes. Install requires explicit approval; execution then runs
        # in the sandbox.
        skill = await self._repo.create_or_replace_pending(
            user_id=user_id,
            name=result.name,
            description=result.description,
            manifest=result.manifest,
            code=result.code,
        )
        return AssistantAuthoringResult(
            message=(
                f"我生成了一個技能「{result.name}」。請檢視程式碼,核可後才會安裝;"
                "安裝後的執行會在受限沙箱中進行。"
            ),
            skill_proposal=_skill_response(skill),
        )

    async def list_skills(
        self,
        *,
        user_id: UUID,
        status: str | None = _INSTALLED,
    ) -> list[AssistantSkillResponse]:
        skills = await self._repo.list_by_status(user_id=user_id, status=status)
        return [_skill_response(skill) for skill in skills]

    async def approve_skill(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkillResponse:
        pending = await self._repo.get_by_id(user_id=user_id, skill_id=skill_id)
        if pending is None:
            raise NotFoundError("Assistant skill not found")
        # Re-validate the manifest at the install gate, not just at draft time.
        validate_manifest(pending.manifest)
        skill = await self._repo.approve(user_id=user_id, skill_id=skill_id)
        if skill is None:
            raise NotFoundError("Assistant skill not found")
        return _skill_response(skill)

    async def execute_skill(
        self,
        *,
        user_id: UUID,
        skill_id: UUID,
        item_id: UUID,
    ) -> AssistantSkillExecuteResponse:
        skill = await self._repo.get_by_id(user_id=user_id, skill_id=skill_id)
        if skill is None or skill.status != _INSTALLED:
            raise NotFoundError("Assistant skill not found")
        if skill.name != INSPECT_DETAILS_SKILL_NAME:
            raise AppError(ErrorCode.INVALID_OPERATION, "Unsupported assistant skill handler")

        item = await self._drive.get_item(user_id=user_id, item_id=item_id)
        return AssistantSkillExecuteResponse(
            skill_id=skill.id,
            skill_name=skill.name,
            item_id=item_id,
            message=f"Details for {item.name}",
            output=_item_output(item),
        )
