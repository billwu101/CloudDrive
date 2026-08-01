from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.assistant.skills.registry import (
    RegisteredSkill,
    SkillContext,
    SkillOutput,
    SkillRegistry,
)
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, InvalidOperationError, NotFoundError
from app.drive.schemas import DriveItemSortField
from app.drive.service import DriveService
from app.schemas.common import SortOrder
from app.search.service import SearchService
from app.trash.service import TrashService
from app.users.service import QuotaService


def build_read_only_registry(
    *,
    drive_service: DriveService,
    search_service: SearchService,
    quota_service: QuotaService,
    trash_service: TrashService,
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

    async def find_folder(context: SkillContext, args: Mapping[str, Any]) -> Any:
        name = _required_str(args, "name")
        page = await search_service.search(
            context.user_id,
            name,
            item_type="FOLDER",
            page=1,
            page_size=_FIND_FOLDER_PAGE_SIZE,
        )
        candidates, total = _paged_items(_dump(page))
        return _exactly_one_folder(name, candidates, total)

    async def recent(context: SkillContext, args: Mapping[str, Any]) -> Any:
        items = await drive_service.get_recent(
            context.user_id,
            limit=_int_arg(args, "limit", default=20, min_value=1, max_value=100),
        )
        return [_dump(item) for item in items]

    async def storage_quota(context: SkillContext, args: Mapping[str, Any]) -> Any:
        quota = await quota_service.get_quota_info(context.user_id)
        return _dump(quota)

    async def list_trash(context: SkillContext, args: Mapping[str, Any]) -> Any:
        page = await trash_service.list_trash(
            context.user_id,
            page=_int_arg(args, "page", default=1, min_value=1),
            page_size=_int_arg(args, "page_size", default=50, min_value=1, max_value=200),
            name=_optional_str(args.get("q")),
        )
        return _dump(page)

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
            output=SkillOutput.PAGED_ITEMS,
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
            output=SkillOutput.ITEM,
        )
    )
    registry.register(
        RegisteredSkill(
            name="search",
            description=(
                "Fuzzy search: matches a substring of the item's name AND the indexed "
                "text content of files. Results are ordered by name, so the first one "
                "is NOT the best match — never assume items.0 is the item the user "
                "meant. To get a folder's id from its name, use find_folder instead. "
                "Returns {items:[{id, name, item_type, ...}], total}."
            ),
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
            output=SkillOutput.PAGED_ITEMS,
        )
    )
    registry.register(
        RegisteredSkill(
            name="find_folder",
            description=(
                "Resolve a FOLDER by its exact name (case-insensitive). Use this — not "
                "search — whenever you need a folder's id from its name, e.g. to list "
                "it, to move something into it, or to empty it. Folders only: a file "
                "with the same name is never returned. It does NOT silently pick one: "
                "if no folder has that name, or several do, or there are too many "
                "candidates to compare, the step fails with a message saying so. "
                "Returns {items:[{id, name, ...}], total: 1} → reference it as "
                '"items.0.id".'
            ),
            parameters=_object_schema(
                {"name": {"type": "string", "description": "Exact folder name."}},
                required=["name"],
            ),
            permission_tier="read",
            handler=find_folder,
            output=SkillOutput.PAGED_ITEMS,
        )
    )
    registry.register(
        RegisteredSkill(
            name="recent",
            description="List recently accessed drive items.",
            parameters=_object_schema({"limit": {"type": "integer", "minimum": 1, "maximum": 100}}),
            permission_tier="read",
            handler=recent,
            output=SkillOutput.ITEM_LIST,
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
    registry.register(
        RegisteredSkill(
            name="list_trash",
            description=(
                "List the items currently in the trash (deleted files and folders). "
                "Trashed items do NOT appear in search or list_items — use this to find "
                "something in the trash before restoring it, or to restore everything. "
                "Pass 'q' to filter by name (e.g. to restore one specific item). "
                "Returns {items:[{id, name, ...}], total}."
            ),
            parameters=_object_schema(
                {
                    "q": {"type": "string", "description": "Filter trashed items by name."},
                    "page": {"type": "integer", "minimum": 1},
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 200},
                }
            ),
            permission_tier="read",
            handler=list_trash,
            output=SkillOutput.PAGED_ITEMS,
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


# The largest page ``search`` accepts. A name lookup that only saw the first 20
# rows would answer "no such folder" while the folder sat on row 21; the total
# that comes back with the page is also what makes the "too many candidates to
# compare" case detectable at all (see _exactly_one_folder).
_FIND_FOLDER_PAGE_SIZE = 200
# How many candidate names a failure message lists before it stops.
_LISTED_CANDIDATES = 5


def _paged_items(output: Any) -> tuple[list[dict[str, Any]], int]:
    """Split a ``{"items": [...], "total": N}`` payload into its two parts.

    Reads the *dumped* payload rather than the ``Page`` model, so it works for
    any search implementation returning the documented shape — the eval
    harness substitutes a plain dict for the real service.
    """

    if not isinstance(output, dict):
        return [], 0
    items = [item for item in output.get("items") or [] if isinstance(item, dict)]
    total = output.get("total")
    return items, total if isinstance(total, int) else len(items)


def _same_name(candidate: Any, name: str) -> bool:
    """Deliberately *not* the drive's own notion of the same name.

    ``DriveRepository.name_exists_in_parent`` compares case-sensitively
    (``DriveItem.name == name``), so "Reports" and "reports" can legitimately
    sit side by side in one folder. A person asking for "reports" means either
    of them, so the match here is case-insensitive — and the divergence is
    safe in this direction: two case variants come back as *ambiguous*, which
    asks the user, rather than as a silent pick.
    """

    return isinstance(candidate, str) and candidate.strip().casefold() == name.casefold()


def _candidate_labels(items: list[dict[str, Any]]) -> str:
    """Name (and modified date, when known) of each candidate, for a message the
    user has to choose from. Ids stay out: a UUID tells the user nothing."""

    labels: list[str] = []
    for item in items[:_LISTED_CANDIDATES]:
        label = str(item.get("name", ""))
        updated = item.get("updated_at")
        if isinstance(updated, str) and updated:
            label += f"(最後更新 {updated[:10]})"
        labels.append(label)
    tail = f" 等 {len(items)} 個" if len(items) > _LISTED_CANDIDATES else ""
    return "、".join(labels) + tail


def _exactly_one_folder(name: str, candidates: list[dict[str, Any]], total: int) -> Any:
    """The one folder named ``name``, or an AppError the user can act on.

    Every failure is raised rather than returned as an empty page. A step that
    hands back ``{"items": []}`` merely moves the failure downstream, where a
    reference to ``items.0.id`` dies with ``cannot resolve path`` — an internal
    string the user can do nothing with. The wording matters because it *is*
    what the user reads: the failure report quotes ``StepResult.error``
    verbatim.

    Several matches are a failure too. Picking one would be picking on the
    user's behalf, and ``ORDER BY name`` makes "the first one" alphabetical
    rather than best — precisely the blind ``items.0`` this skill exists to
    replace.
    """

    if total > _FIND_FOLDER_PAGE_SIZE:
        raise InvalidOperationError(
            f"名稱含有「{name}」的資料夾有 {total} 個,超過一次能比對的上限"
            f"({_FIND_FOLDER_PAGE_SIZE} 個),無法判斷是哪一個。請給更完整的名稱。"
        )
    folders = [item for item in candidates if _is_folder(item)]
    matches = [item for item in folders if _same_name(item.get("name"), name)]
    if not matches:
        hint = f"名稱含有「{name}」的資料夾有:{_candidate_labels(folders)}。" if folders else ""
        raise NotFoundError(f"找不到名為「{name}」的資料夾。{hint}")
    if len(matches) > 1:
        raise InvalidOperationError(
            f"有 {len(matches)} 個資料夾都叫「{name}」:{_candidate_labels(matches)}。"
            "請告訴我要用哪一個。"
        )
    return {"items": matches, "total": len(matches)}


def _is_folder(item: Mapping[str, Any]) -> bool:
    """Belt and braces: ``search`` was already asked for FOLDER only, but the
    whole point of this skill is that a file must never be handed back as a
    destination folder."""

    return str(item.get("item_type", "")).upper() == "FOLDER"


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


# The model spells "the root folder" as a sentinel string ("root"/"null"/…) far
# more often than it passes null — an unambiguous intent that must not crash the
# whole listing. Map these to None (root); a genuine non-UUID still errors.
_ROOT_SENTINELS = {"root", "root_folder", "null", "none", "/"}


def _optional_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        return None
    if value.strip().lower() in _ROOT_SENTINELS:
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
