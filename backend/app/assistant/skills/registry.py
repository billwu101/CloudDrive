from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.assistant.llm.client import LLMToolDefinition
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


class SkillOutput(StrEnum):
    """What a skill returns, in the terms a step reference cares about.

    A plan references an earlier step as ``{"from": i, "path": "items.0.id"}``,
    and whether that path resolves depends entirely on the shape the referenced
    skill returns. Declaring the shape lets ``validate_plan`` reject an
    impossible reference while it can still be repaired, instead of letting it
    surface at execution time as ``cannot resolve path`` — after earlier write
    steps have already run.

    ``MUTATED_ITEM`` is deliberately distinct from ``ITEM``: both are a single
    item, but a mutated item is *the one the step acted on*, so referencing it
    as a destination folder is a plan error (observed repeatedly: the model
    loses track of its own step numbering and points ``parent_id`` at a
    ``move_item``). ``OPAQUE`` means "not a useful reference source" and is the
    default, so self-built skills — whose return value we cannot know — are
    never validated against a shape they may not have.
    """

    PAGED_ITEMS = "paged_items"  # {"items": [...], "total": N} → "items.0.id"
    ITEM_LIST = "item_list"  # [ ... ]                     → "0.id"
    ITEM = "item"  # the item itself             → "id"
    NEW_FOLDER = "new_folder"  # an item, and known to be a folder
    MUTATED_ITEM = "mutated_item"  # the item this step just changed
    OPAQUE = "opaque"


@dataclass(frozen=True)
class SkillContext:
    user_id: UUID


SkillHandler = Callable[[SkillContext, Mapping[str, Any]], Awaitable[Any]]


@dataclass(frozen=True)
class RegisteredSkill:
    name: str
    description: str
    parameters: dict[str, Any]
    permission_tier: str
    handler: SkillHandler
    # True for self-built skills: the planner does not fill ``item_id`` — it is
    # injected from the user's selected files, once per file (batch).
    requires_selection: bool = False
    # What this skill returns (see SkillOutput). Defaults to OPAQUE so a skill
    # that does not declare a shape is simply not reference-checked.
    output: SkillOutput = SkillOutput.OPAQUE

    def to_tool_definition(self) -> LLMToolDefinition:
        return LLMToolDefinition(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
        )


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, RegisteredSkill] = {}

    def register(self, skill: RegisteredSkill) -> None:
        if skill.name in self._skills:
            raise AppError(ErrorCode.INVALID_OPERATION, f"Skill already registered: {skill.name}")
        self._skills[skill.name] = skill

    def list_skills(self) -> list[RegisteredSkill]:
        return list(self._skills.values())

    def get(self, name: str) -> RegisteredSkill | None:
        return self._skills.get(name)

    def tool_definitions(self) -> list[LLMToolDefinition]:
        return [skill.to_tool_definition() for skill in self.list_skills()]

    async def execute(
        self,
        *,
        name: str,
        context: SkillContext,
        arguments: Mapping[str, Any],
    ) -> Any:
        skill = self._skills.get(name)
        if skill is None:
            raise AppError(ErrorCode.INVALID_OPERATION, f"Unknown assistant skill: {name}")
        return await skill.handler(context, arguments)
