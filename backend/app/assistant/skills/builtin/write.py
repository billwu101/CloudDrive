from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.service import DriveService
from app.permission.permissions import Permission
from app.share.service import ShareLinkService
from app.trash.service import TrashService

_WRITE = "write"
_DESTRUCTIVE = "destructive"


def register_write_skills(
    registry: SkillRegistry,
    *,
    drive_service: DriveService,
    trash_service: TrashService | None = None,
    share_link_service: ShareLinkService | None = None,
) -> None:
    """Register non-read (write/destructive) built-in skills.

    These carry a non-``read`` permission tier, so the workflow pipeline marks
    them ``requires_approval`` — they only run after the user confirms the plan
    (see ``permissions.classify_steps``). Trash/restore skills are registered
    only when a ``trash_service`` is supplied.
    """

    async def create_folder(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await drive_service.create_folder(
            context.user_id, _optional_uuid(args.get("parent_id")), _required_str(args, "name")
        )
        return _dump(item)

    async def rename_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await drive_service.rename(
            context.user_id, _required_uuid(args, "item_id"), _required_str(args, "new_name")
        )
        return _dump(item)

    async def move_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await drive_service.move(
            context.user_id, _required_uuid(args, "item_id"), _optional_uuid(args.get("parent_id"))
        )
        return _dump(item)

    async def star_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await drive_service.set_starred(
            context.user_id, _required_uuid(args, "item_id"), _required_bool(args, "starred")
        )
        return _dump(item)

    async def organize_by_type(context: SkillContext, args: Mapping[str, Any]) -> Any:
        # Composite: move every loose file in the root into a per-extension folder.
        page = await drive_service.list_items(context.user_id, None, page=1, page_size=200)
        items = list(page.items)
        folders = {i.name: i for i in items if i.item_type == "FOLDER"}
        moved = 0
        used: set[str] = set()
        for item in items:
            if item.item_type != "FILE":
                continue
            ext = (item.extension or "other").lower()
            folder_name = f"{ext}-files"
            folder = folders.get(folder_name)
            if folder is None:
                folder = await drive_service.create_folder(context.user_id, None, folder_name)
                folders[folder_name] = folder
            await drive_service.move(context.user_id, item.id, folder.id)
            moved += 1
            used.add(folder_name)
        return {"moved_files": moved, "folders": sorted(used)}

    registry.register(
        RegisteredSkill(
            name="create_folder",
            description=(
                "Create a new folder. Call this when the user asks to create, make, "
                "or add a folder."
            ),
            parameters=_object_schema(
                {
                    "name": {"type": "string", "description": "New folder name."},
                    "parent_id": _nullable_uuid("Parent folder UUID; null/omitted for the root."),
                },
                required=["name"],
            ),
            permission_tier=_WRITE,
            handler=create_folder,
        )
    )
    registry.register(
        RegisteredSkill(
            name="rename_item",
            description=(
                "Rename a file or folder. Call this when the user asks to rename something."
            ),
            parameters=_object_schema(
                {
                    "item_id": {"type": "string", "description": "UUID of the item to rename."},
                    "new_name": {"type": "string", "description": "New name."},
                },
                required=["item_id", "new_name"],
            ),
            permission_tier=_WRITE,
            handler=rename_item,
        )
    )
    registry.register(
        RegisteredSkill(
            name="move_item",
            description=(
                "Move a file or folder into another folder. Call this when the user asks to "
                "move something."
            ),
            parameters=_object_schema(
                {
                    "item_id": {"type": "string", "description": "UUID of the item to move."},
                    "parent_id": _nullable_uuid("Destination folder UUID; null/omitted for root."),
                },
                required=["item_id"],
            ),
            permission_tier=_WRITE,
            handler=move_item,
        )
    )
    registry.register(
        RegisteredSkill(
            name="star_item",
            description="Star or unstar a file or folder.",
            parameters=_object_schema(
                {
                    "item_id": {"type": "string", "description": "UUID of the item."},
                    "starred": {"type": "boolean", "description": "True to star, false to unstar."},
                },
                required=["item_id", "starred"],
            ),
            permission_tier=_WRITE,
            handler=star_item,
        )
    )
    registry.register(
        RegisteredSkill(
            name="organize_by_type",
            description=(
                "Organize the root: move loose files into per-extension folders "
                "(e.g. pdf-files, jpg-files). Call when the user asks to tidy or sort by type."
            ),
            parameters=_object_schema({}, required=[]),
            permission_tier=_WRITE,
            handler=organize_by_type,
        )
    )

    if share_link_service is not None:

        async def share_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
            link = await share_link_service.create_link(
                context.user_id, _required_uuid(args, "item_id"), Permission.VIEWER
            )
            return _dump(link)

        registry.register(
            RegisteredSkill(
                name="share_item",
                description=(
                    "Create a public view-only share link for a file or folder. "
                    "Call when the user asks to share something or get a shareable link."
                ),
                parameters=_object_schema(
                    {"item_id": {"type": "string", "description": "UUID of the item to share."}},
                    required=["item_id"],
                ),
                permission_tier=_WRITE,
                handler=share_item,
            )
        )

    if trash_service is not None:
        _register_trash_skills(registry, trash_service=trash_service)


def _register_trash_skills(registry: SkillRegistry, *, trash_service: TrashService) -> None:
    async def trash_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await trash_service.trash_item(context.user_id, _required_uuid(args, "item_id"))
        return _dump(item)

    async def restore_item(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await trash_service.restore(context.user_id, _required_uuid(args, "item_id"))
        return _dump(item)

    registry.register(
        RegisteredSkill(
            name="trash_item",
            description=(
                "Move a file or folder to the trash. Call this when the user asks to delete, "
                "remove, or trash something."
            ),
            parameters=_object_schema(
                {"item_id": {"type": "string", "description": "UUID of the item to trash."}},
                required=["item_id"],
            ),
            permission_tier=_DESTRUCTIVE,
            handler=trash_item,
        )
    )
    registry.register(
        RegisteredSkill(
            name="restore_item",
            description="Restore a file or folder from the trash.",
            parameters=_object_schema(
                {"item_id": {"type": "string", "description": "UUID of the item to restore."}},
                required=["item_id"],
            ),
            permission_tier=_WRITE,
            handler=restore_item,
        )
    )


def _object_schema(properties: dict[str, Any], *, required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _nullable_uuid(description: str) -> dict[str, Any]:
    return {"type": ["string", "null"], "description": description}


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _required_str(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppError(ErrorCode.INVALID_OPERATION, f"Missing required argument: {key}")
    return value.strip()


def _required_bool(args: Mapping[str, Any], key: str) -> bool:
    value = args.get(key)
    if not isinstance(value, bool):
        raise AppError(ErrorCode.INVALID_OPERATION, f"Argument must be a boolean: {key}")
    return value


def _required_uuid(args: Mapping[str, Any], key: str) -> UUID:
    value = args.get(key)
    if not isinstance(value, str):
        raise AppError(ErrorCode.INVALID_OPERATION, f"Missing required UUID argument: {key}")
    return _parse_uuid(value, key)


def _optional_uuid(value: Any) -> UUID | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if not isinstance(value, str):
        raise AppError(ErrorCode.INVALID_OPERATION, "Expected a UUID string or null")
    return _parse_uuid(value, "parent_id")


def _parse_uuid(value: str, key: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise AppError(ErrorCode.INVALID_OPERATION, f"Invalid UUID for argument: {key}") from exc
