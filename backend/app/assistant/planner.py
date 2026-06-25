from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.registry import SkillRegistry
from app.assistant.workflow import PlannedStep, is_step_ref

# Structured-output schema for the plan, sent as ``response_format`` on external
# models so they emit the exact ``{reply, steps[...]}`` shape (local Ollama already
# follows it; external models like Gemini otherwise reply in free text). Not
# "strict" so the open ``arguments`` object stays valid across providers.
_PLAN_RESPONSE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "workflow_plan",
        "schema": {
            "type": "object",
            "properties": {
                "reply": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "skill": {"type": "string"},
                            "arguments": {"type": "object"},
                            "depends_on": {"type": "array", "items": {"type": "integer"}},
                        },
                        "required": ["skill", "arguments", "depends_on"],
                    },
                },
            },
            "required": ["reply", "steps"],
        },
    },
}


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
        "- Never invent a skill that is not listed, and always include every required argument.\n"
        "- Skills are composable. An argument value may be a literal, OR a reference to an earlier "
        'step\'s output: {"from_step": <earlier index>, "path": "items.0.id"}. search and '
        'list_items return {"items": [{"id", "name", "item_type", ...}], "total": N}.\n'
        "- Never guess a UUID. To act on something you only know by name (e.g. a folder), search "
        'for it first, then reference the result. Example — "what is in the test folder": '
        '[{"skill": "search", "arguments": {"q": "test"}}, {"skill": "list_items", "arguments": '
        '{"parent_id": {"from_step": 0, "path": "items.0.id"}}}].\n'
        "- Output JSON only, no prose, no code fences.\n\n"
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


def validate_plan(steps: list[PlannedStep], registry: SkillRegistry) -> list[str]:
    """Semantic validation of a planned workflow against the skill catalog.

    Catches the classes of failure a JSON-parse check misses: a hallucinated
    skill, or a step that omits a required argument (e.g. ``search`` without
    ``q``). Returns a list of human-readable problems ([] means the plan is
    executable).
    """

    problems: list[str] = []
    for index, step in enumerate(steps):
        skill = registry.get(step.skill)
        if skill is None:
            problems.append(f"step {index}: unknown skill '{step.skill}'")
            continue
        for arg_value in step.arguments.values():
            if is_step_ref(arg_value):
                from_step = arg_value.get("from_step")
                if not isinstance(from_step, int) or from_step < 0 or from_step >= index:
                    problems.append(
                        f"step {index}: reference must point to an earlier step, got {from_step}"
                    )
        required = skill.parameters.get("required", [])
        if isinstance(required, list):
            for arg in required:
                value = step.arguments.get(arg)
                missing = value is None or (isinstance(value, str) and not value.strip())
                if missing and not is_step_ref(value):
                    problems.append(
                        f"step {index}: skill '{step.skill}' is missing required argument '{arg}'"
                    )
    return problems


class WorkflowPlanner:
    def __init__(
        self,
        *,
        llm: ModelRouter,
        registry: SkillRegistry,
        context: ContextManager,
        num_ctx: int,
        max_repair: int = 2,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._context = context
        self._num_ctx = num_ctx
        self._max_repair = max(0, max_repair)

    async def plan(
        self, *, message: str, target: str | None = None, selected_count: int = 0
    ) -> PlanResult:
        messages = [
            LLMMessage(role="system", content=build_planner_prompt(self._registry)),
        ]
        # Tell the planner about the user's current file selection so skills that
        # operate on selected files can be used directly, without asking which file.
        if selected_count > 0:
            messages.append(
                LLMMessage(
                    role="system",
                    content=(
                        f"The user currently has {selected_count} file(s) selected. "
                        "Skills that operate on the user's selected file(s) can be used "
                        "directly on the selection — do NOT ask which file; just call the "
                        "skill (its item_id is supplied automatically per selected file)."
                    ),
                )
            )
        messages.append(LLMMessage(role="user", content=message))

        def _valid(response: LLMResponse) -> bool:
            return _parse(response.content) is not None

        last_reply = "I could not plan that request."
        # Each iteration: get a JSON plan (ModelRouter handles model-level retry +
        # privacy-gated escalation), then semantically validate it against the
        # skills. On problems, feed them back and re-plan — so a deeper / ambiguous
        # request that first yields an invalid call (e.g. search without q) gets
        # corrected instead of failing at execution.
        for attempt in range(self._max_repair + 1):
            response = await self._llm.chat(
                self._context.trim(messages),
                [],
                num_ctx=self._num_ctx,
                validator=_valid,
                target=target,
                response_format=_PLAN_RESPONSE_FORMAT,
            )
            result = _parse(response.content)
            if result is None:
                return PlanResult(reply=response.content.strip() or last_reply)
            last_reply = result.reply or last_reply
            problems = validate_plan(result.steps, self._registry)
            if not problems:
                return result
            if attempt < self._max_repair:
                messages.append(LLMMessage(role="assistant", content=response.content))
                messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "Your previous plan was invalid: "
                            + "; ".join(problems)
                            + ". Re-plan using only the listed skills and include every required "
                            "argument. If you cannot satisfy the request with the available "
                            "skills, return an empty steps list and explain briefly in reply."
                        ),
                    )
                )

        # Repairs exhausted — never execute an invalid plan; answer conversationally.
        return PlanResult(
            reply=(
                last_reply
                if last_reply != "I could not plan that request."
                else "I couldn't turn that into a valid action with the tools I have. "
                "Could you rephrase or be more specific?"
            ),
            steps=[],
        )
