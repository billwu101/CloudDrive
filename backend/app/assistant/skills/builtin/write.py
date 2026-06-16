from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.service import DriveService


def register_write_skills(registry: SkillRegistry, *, drive_service: DriveService) -> None:
    """Register non-read (write) built-in skills.

    Write skills carry the ``write`` permission tier, so the workflow pipeline
    classifies them as ``requires_approval`` — they only run after the user
    confirms the plan (see ``permissions.classify_steps``).
    """

    async def create_folder(context: SkillContext, args: Mapping[str, Any]) -> Any:
        name = _required_str(args, "name")
        parent_id = _optional_uuid(args.get("parent_id"))
        item = await drive_service.create_folder(context.user_id, parent_id, name)
        return _dump(item)

    registry.register(
        RegisteredSkill(
            name="create_folder",
            description=(
                "Create a new folder. Call this when the user asks to create, make, "
                "or add a folder."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "New folder name."},
                    "parent_id": {
                        "type": ["string", "null"],
                        "description": "Parent folder UUID; null or omitted for the root.",
                    },
                },
                "required": ["name"],
                "additionalProperties": False,
            },
            permission_tier="write",
            handler=create_folder,
        )
    )


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _required_str(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppError(ErrorCode.INVALID_OPERATION, f"Missing required argument: {key}")
    return value.strip()


def _optional_uuid(value: Any) -> UUID | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise AppError(ErrorCode.INVALID_OPERATION, "parent_id must be a string or null")
    try:
        return UUID(value)
    except ValueError as exc:
        raise AppError(ErrorCode.INVALID_OPERATION, "Invalid UUID for parent_id") from exc
