from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.registry import SkillRegistry
from app.assistant.workflow import (
    PlannedStep,
    is_reference,
    is_step_ref,
    ref_source,
)


# Structured-output schema for the plan, sent as ``response_format`` on external
# models so they emit the exact ``{reply, steps[...]}`` shape (local Ollama already
# follows it; external models like Gemini otherwise reply in free text). Not
# "strict" so the open ``arguments`` object stays valid across providers.
def _plan_response_format(skill_names: list[str] | None = None) -> dict[str, object]:
    skill_schema: dict[str, object] = {"type": "string"}
    if skill_names:
        skill_schema["enum"] = skill_names
    return {
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
                                "skill": skill_schema,
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


_PLAN_RESPONSE_FORMAT: dict[str, object] = _plan_response_format()


def build_plan_response_format(registry: SkillRegistry) -> dict[str, object]:
    """Plan schema with ``skill`` constrained to the registry's real names.

    Constrained decoding then makes a hallucinated skill name unrepresentable —
    the grammar masks it at sampling time instead of `classify_steps` rejecting
    it after the fact (DEC-032). Built per request because installed self-built
    skills change the registry; names are sorted for a stable schema. An empty
    registry falls back to a free string (an empty enum is invalid JSON Schema).
    """
    names = sorted(skill.name for skill in registry.list_skills())
    return _plan_response_format(names or None)


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
        "- Skills are composable. Any argument value may be a literal OR a reference. "
        "Two kinds of reference:\n"
        '  (a) an earlier step\'s output: {"from": <earlier index>, "path": "items.0.id"}. '
        'search and list_items return {"items": [{"id", "name", "item_type", ...}], "total": N}.\n'
        '  (b) the user\'s current file selection: {"from": "selection", "item": <i>} for one '
        'selected file, or {"from": "selection", "each": true} to act on EVERY selected file '
        "(the step runs once per file; the other arguments are copied to each).\n"
        "- Never guess or write a UUID. To act on something you only know by name (e.g. a "
        "folder), search for it first, then reference the result. To act on the user's selected "
        "file(s), use a selection reference — do NOT ask which file.\n"
        '  Example — "what is in the test folder": '
        '[{"skill": "search", "arguments": {"q": "test"}}, {"skill": "list_items", "arguments": '
        '{"parent_id": {"from": 0, "path": "items.0.id"}}}].\n'
        '  Example — "move the selected files into test2": '
        '[{"skill": "search", "arguments": {"q": "test2"}}, {"skill": "move_item", "arguments": '
        '{"item_id": {"from": "selection", "each": true}, '
        '"parent_id": {"from": 0, "path": "items.0.id"}}}].\n'
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
        # Mirror classify_steps' dependency rule here so a bad depends_on (self/
        # forward reference) triggers the repair loop instead of surfacing as a
        # 400 from the permission layer after planning succeeded (DEC-032).
        for dependency in step.depends_on:
            if dependency < 0 or dependency >= index:
                problems.append(
                    f"step {index}: depends_on must point to an earlier step, got {dependency}"
                )
        for arg_value in step.arguments.values():
            # Step-output references must point at an earlier step. Selection
            # references are always resolvable (the selection exists independently
            # of step order), so they are exempt from the earlier-step rule.
            if is_step_ref(arg_value):
                from_step = ref_source(arg_value)
                if not isinstance(from_step, int) or from_step < 0 or from_step >= index:
                    problems.append(
                        f"step {index}: reference must point to an earlier step, got {from_step}"
                    )
        required = skill.parameters.get("required", [])
        if isinstance(required, list):
            for arg in required:
                value = step.arguments.get(arg)
                missing = value is None or (isinstance(value, str) and not value.strip())
                # A reference (step-output or selection) counts as supplied.
                if missing and not is_reference(value):
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
        disable_thinking: bool | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._context = context
        self._num_ctx = num_ctx
        self._max_repair = max(0, max_repair)
        # DEC-033: planning runs with Ollama's thinking phase disabled by default
        # (E8 — cured repetition loops, ~10x faster, no plan-quality loss). Passed
        # through to every plan() chat call; None defers to the client default.
        self._disable_thinking = disable_thinking

    async def plan(
        self,
        *,
        message: str,
        target: str | None = None,
        selected_items: list[dict[str, object]] | None = None,
        history: list[LLMMessage] | None = None,
    ) -> PlanResult:
        selected = selected_items or []
        messages = [
            LLMMessage(role="system", content=build_planner_prompt(self._registry)),
        ]
        # Tell the planner about the user's current file selection so it can
        # reference selected files directly (never guessing a UUID). Files are
        # listed by short handle + name; the model references them by index.
        if selected:
            listing = "  ".join(f"[{i}] {item.get('name', '?')}" for i, item in enumerate(selected))
            messages.append(
                LLMMessage(
                    role="system",
                    content=(
                        f"The user currently has {len(selected)} file(s) selected: {listing}. "
                        'Reference a specific one as {"from": "selection", "item": i} or all of '
                        'them as {"from": "selection", "each": true}. Do NOT ask which file, and '
                        "never write their UUIDs."
                    ),
                )
            )
        # Prior turns (conversation memory) sit between the system framing and the
        # current request so references like "rename the first one" resolve against
        # what actually ran. ContextManager.trim caps the total below num_ctx.
        if history:
            messages.extend(history)
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
                response_format=build_plan_response_format(self._registry),
                disable_thinking=self._disable_thinking,
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
