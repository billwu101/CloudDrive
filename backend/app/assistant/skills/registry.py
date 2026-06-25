from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.assistant.llm.client import LLMToolDefinition
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError


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
