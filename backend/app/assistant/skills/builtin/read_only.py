from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.assistant.skills.registry import RegisteredSkill, SkillContext, SkillRegistry
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.schemas import DriveItemSortField
from app.drive.service import DriveService
from app.schemas.common import SortOrder
from app.search.service import SearchService
from app.users.service import QuotaService


def build_read_only_registry(
    *,
    drive_service: DriveService,
    search_service: SearchService,
    quota_service: QuotaService,
) -> SkillRegistry:
    registry = SkillRegistry()

    async def list_items(context: SkillContext, args: Mapping[str, Any]) -> Any:
        page = await drive_service.list_items(
            context.user_id,
            _optional_uuid(args.get("parent_id")),
            page=_int_arg(args, "page", default=1, min_value=1),
            page_size=_int_arg(args, "page_size", default=20, min_value=1, max_value=200),
            sort_by=_sort_field(args.get("sort_by")),
            order=_sort_order(args.get("order")),
        )
        return _dump(page)

    async def get_info(context: SkillContext, args: Mapping[str, Any]) -> Any:
        item = await drive_service.get_item(context.user_id, _required_uuid(args, "item_id"))
        return _dump(item)

    async def search(context: SkillContext, args: Mapping[str, Any]) -> Any:
        query = _required_str(args, "q")
        page = await search_service.search(
            context.user_id,
            query,
            item_type=_optional_str(args.get("item_type")),
            mime_type=_optional_str(args.get("mime_type")),
            page=_int_arg(args, "page", default=1, min_value=1),
            page_size=_int_arg(args, "page_size", default=20, min_value=1, max_value=200),
        )
        return _dump(page)

    async def recent(context: SkillContext, args: Mapping[str, Any]) -> Any:
        items = await drive_service.get_recent(
            context.user_id,
            limit=_int_arg(args, "limit", default=20, min_value=1, max_value=100),
        )
        return [_dump(item) for item in items]

    async def storage_quota(context: SkillContext, args: Mapping[str, Any]) -> Any:
        quota = await quota_service.get_quota_info(context.user_id)
        return _dump(quota)

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List files and folders in the user's root or a folder.",
            parameters=_object_schema(
                {
                    "parent_id": {"type": ["string", "null"], "description": "Folder UUID."},
                    "page": {"type": "integer", "minimum": 1},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 200},
                    "sort_by": {
                        "type": "string",
                        "enum": ["name", "created_at", "updated_at", "size_bytes"],
                    },
                    "order": {"type": "string", "enum": ["asc", "desc"]},
                }
            ),
            permission_tier="read",
            handler=list_items,
        )
    )
    registry.register(
        RegisteredSkill(
            name="get_info",
            description="Get metadata for one file or folder by UUID.",
            parameters=_object_schema(
                {"item_id": {"type": "string", "description": "Drive item UUID."}},
                required=["item_id"],
            ),
            permission_tier="read",
            handler=get_info,
        )
    )
    registry.register(
        RegisteredSkill(
            name="search",
            description="Search the user's drive items by name.",
            parameters=_object_schema(
                {
                    "q": {"type": "string"},
                    "item_type": {"type": ["string", "null"], "enum": ["FILE", "FOLDER", None]},
                    "mime_type": {"type": ["string", "null"]},
                    "page": {"type": "integer", "minimum": 1},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 200},
                },
                required=["q"],
            ),
            permission_tier="read",
            handler=search,
        )
    )
    registry.register(
        RegisteredSkill(
            name="recent",
            description="List recently accessed drive items.",
            parameters=_object_schema({"limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
            permission_tier="read",
            handler=recent,
        )
    )
    registry.register(
        RegisteredSkill(
            name="storage_quota",
            description="Get the user's storage quota and usage.",
            parameters=_object_schema({}),
            permission_tier="read",
            handler=storage_quota,
        )
    )
    return registry


def _object_schema(
    properties: dict[str, Any],
    *,
    required: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _dump(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _required_str(args: Mapping[str, Any], key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AppError(ErrorCode.INVALID_OPERATION, f"Missing required argument: {key}")
    return value.strip()


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise AppError(ErrorCode.INVALID_OPERATION, "Expected string or null")
    normalized = value.strip()
    return normalized or None


def _required_uuid(args: Mapping[str, Any], key: str) -> UUID:
    value = args.get(key)
    if not isinstance(value, str):
        raise AppError(ErrorCode.INVALID_OPERATION, f"Missing required UUID argument: {key}")
    return _parse_uuid(value, key)


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    return _parse_uuid(value, "parent_id")


def _parse_uuid(value: str, key: str) -> UUID:
    try:
        return UUID(value)
    except ValueError as exc:
        raise AppError(ErrorCode.INVALID_OPERATION, f"Invalid UUID for argument: {key}") from exc


def _int_arg(
    args: Mapping[str, Any],
    key: str,
    *,
    default: int,
    min_value: int,
    max_value: int | None = None,
) -> int:
    value = args.get(key, default)
    if not isinstance(value, int):
        raise AppError(ErrorCode.INVALID_OPERATION, f"Argument must be an integer: {key}")
    if value < min_value or (max_value is not None and value > max_value):
        raise AppError(ErrorCode.INVALID_OPERATION, f"Argument out of range: {key}")
    return value


def _sort_field(value: Any) -> DriveItemSortField:
    if value is None:
        return DriveItemSortField.NAME
    if isinstance(value, str):
        try:
            return DriveItemSortField(value)
        except ValueError as exc:
            raise AppError(ErrorCode.INVALID_OPERATION, "Invalid sort_by") from exc
    raise AppError(ErrorCode.INVALID_OPERATION, "Invalid sort_by")


def _sort_order(value: Any) -> SortOrder:
    if value is None:
        return SortOrder.ASC
    if isinstance(value, str):
        try:
            return SortOrder(value)
        except ValueError as exc:
            raise AppError(ErrorCode.INVALID_OPERATION, "Invalid order") from exc
    raise AppError(ErrorCode.INVALID_OPERATION, "Invalid order")
