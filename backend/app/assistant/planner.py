from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.registry import SkillRegistry
from app.assistant.workflow import PlannedStep


class PlanResult(BaseModel):
    reply: str = ""
    steps: list[PlannedStep] = Field(default_factory=list)


def build_planner_prompt(registry: SkillRegistry) -> str:
    skills = "\n".join(
        f"- {skill.name} ({skill.permission_tier}): {skill.description}"
        for skill in registry.list_skills()
    )
    return (
        "You are CloudDrive's planner. Convert the user's request into a JSON plan "
        "that uses ONLY the available skills.\n"
        'Respond with a single JSON object: {"reply": string, "steps": '
        '[{"skill": string, "arguments": object, "depends_on": [int]}]}.\n'
        "- reply: a short natural-language answer or summary for the user.\n"
        "- steps: ordered skill calls. depends_on lists indices of earlier steps.\n"
        "- If the request needs no drive action, return an empty steps array and answer in reply.\n"
        "- Never invent a skill that is not listed. Output JSON only, no prose, no code fences.\n\n"
        "Available skills:\n"
        f"{skills}"
    )


def _extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _parse(content: str) -> PlanResult | None:
    try:
        data = json.loads(_extract_json(content))
        return PlanResult.model_validate(data)
    except (json.JSONDecodeError, ValidationError, TypeError):
        return None


class WorkflowPlanner:
    def __init__(
        self,
        *,
        llm: ModelRouter,
        registry: SkillRegistry,
        context: ContextManager,
        num_ctx: int,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._context = context
        self._num_ctx = num_ctx

    async def plan(self, *, message: str) -> PlanResult:
        messages = [
            LLMMessage(role="system", content=build_planner_prompt(self._registry)),
            LLMMessage(role="user", content=message),
        ]

        def _valid(response: LLMResponse) -> bool:
            return _parse(response.content) is not None

        # ModelRouter handles local-retry + privacy-gated external escalation; the
        # validator forces a re-plan when the model returns malformed JSON.
        response = await self._llm.chat(
            self._context.trim(messages),
            [],
            num_ctx=self._num_ctx,
            validator=_valid,
        )
        result = _parse(response.content)
        if result is None:
            return PlanResult(reply=response.content.strip() or "I could not plan that request.")
        return result
