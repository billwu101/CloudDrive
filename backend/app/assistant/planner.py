from __future__ import annotations

import json

from pydantic import BaseModel, Field, PrivateAttr, ValidationError

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.registry import RegisteredSkill, SkillOutput, SkillRegistry
from app.assistant.workflow import (
    PlannedStep,
    is_reference,
    is_step_ref,
    ref_source,
)
from app.core.config import get_settings


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
                    "needs_followup": {"type": "boolean"},
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
                "required": ["reply", "steps", "needs_followup"],
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
    # Set by the model when it cannot decide which items to act on until it has
    # seen a query's result: it plans only the read steps and asks to be called
    # again with the actual output. A PUBLIC field, unlike the llm_meta
    # diagnostics below — the model genuinely produces this one, so it belongs
    # in the constrained-decoding schema.
    needs_followup: bool = False
    # Diagnostics from the planning LLM call that produced this result (see
    # LLMResponse) — surfaced for eval/observability by the service layer
    # (AssistantChatResponse.llm_meta). Deliberately PrivateAttr, not a public
    # field: PlanResult doubles as the model's own JSON output schema for
    # constrained decoding (_PLAN_RESPONSE_FORMAT, kept in sync by
    # test_plan_response_format_stays_in_sync_with_models) — the model neither
    # produces nor should be asked to produce these values.
    _done_reason: str | None = PrivateAttr(default=None)
    _prompt_tokens: int | None = PrivateAttr(default=None)
    _completion_tokens: int | None = PrivateAttr(default=None)

    @property
    def done_reason(self) -> str | None:
        return self._done_reason

    @property
    def prompt_tokens(self) -> int | None:
        return self._prompt_tokens

    @property
    def completion_tokens(self) -> int | None:
        return self._completion_tokens

    def _copy_llm_meta(self, other: PlanResult) -> None:
        """Carry diagnostics across when one PlanResult supersedes another (the
        two-phase planner combines two passes into one plan)."""
        self._done_reason = other._done_reason
        self._prompt_tokens = other._prompt_tokens
        self._completion_tokens = other._completion_tokens

    def _set_llm_meta(self, response: LLMResponse) -> None:
        self._done_reason = response.done_reason
        self._prompt_tokens = response.prompt_tokens
        self._completion_tokens = response.completion_tokens


def build_planner_prompt(registry: SkillRegistry, *, two_phase: bool = False) -> str:
    """``two_phase``: whether the caller will actually run a second planning pass.

    The needs_followup instruction MUST NOT be taught when it will not be
    honoured. Teaching it unconditionally regressed the default configuration
    hard: the model split the work, returned only the read-only lookups, and —
    with no second pass to append the writes — the request silently completed
    as a plain listing. Measured on 20 M3 cases against the real model: 7/20
    passed with two-phase on, 0/20 with it off but the instruction still in the
    prompt (every failure ``state_mismatch``, the write step simply missing).
    """

    skills = "\n".join(
        f"- {skill.name} ({skill.permission_tier}): {skill.description}"
        for skill in registry.list_skills()
    )
    followup_rule = (
        "- needs_followup: set it to true ONLY when you cannot tell which items to act "
        "on until you have seen a query's result — e.g. the user wants files sorted by "
        "what they are, and you must read their names first. When you set it to true, "
        "the steps you return must be READ-ONLY lookups (search, list_items, get_info, "
        "recent, storage_quota, list_trash) and NOTHING else: no creating, renaming, "
        "moving, starring or deleting, not even preparation like creating the "
        "destination folder. Those come afterwards — you will be asked again with the "
        "actual results and can then plan every remaining step, referencing the lookups "
        "by index. Otherwise set needs_followup to false and plan the whole request now.\n"
        if two_phase
        else "- needs_followup: always false. Plan the COMPLETE request now, including "
        "every write step; you will not be called again.\n"
    )
    return (
        "You are CloudDrive's planner. Convert the user's request into a JSON plan "
        "that uses ONLY the available skills.\n"
        'Respond with a single JSON object: {"reply": string, "needs_followup": bool, '
        '"steps": [{"skill": string, "arguments": object, "depends_on": [int]}]}.\n'
        "- reply: a short natural-language answer or summary for the user.\n"
        "- steps: ordered skill calls. depends_on lists indices of earlier steps.\n"
        "- If the request needs no drive action, return an empty steps array and answer in reply.\n"
        "- Never invent a skill that is not listed, and always include every required argument.\n"
        "- Skills are composable. Any argument value may be a literal OR a reference. "
        "Two kinds of reference:\n"
        '  (a) an earlier step\'s output: {"from": <earlier index>, "path": "items.0.id"}. '
        'To act on EVERY item a step returned, put "*" where the list index goes: '
        '{"from": <index>, "path": "items.*.id"} — the step then runs once per item.\n'
        "  The path depends on what that step returns — pick the matching shape:\n"
        '  - search, list_items, list_trash return {"items": [{"id", "name", "item_type", ...}], '
        '"total": N} → use "items.0.id" (or "items.*.id").\n'
        '  - recent returns a plain list of items → use "0.id" (or "*.id").\n'
        "  - get_info, create_folder, rename_item, move_item, star_item, trash_item, "
        "restore_item return the ITEM ITSELF, "
        'not a list → use "id". For example, to put files into a folder you just created at '
        'step 1: {"parent_id": {"from": 1, "path": "id"}} — "items.0.id" would fail there.\n'
        '  (b) the user\'s current file selection: {"from": "selection", "item": <i>} for one '
        'selected file, or {"from": "selection", "each": true} to act on EVERY selected file '
        "(the step runs once per file; the other arguments are copied to each).\n"
        "- Never guess or write a UUID. To act on something you only know by name (e.g. a "
        "folder), search for it first, then reference the result. To act on the user's selected "
        "file(s), use a selection reference — do NOT ask which file.\n"
        "- Trashed items are NOT returned by search or list_items. To restore something from the "
        'trash, use list_trash (pass "q" to filter by name) and reference ITS result — never '
        "search for a trashed item. Example — restore the folder named test3 from trash: "
        '[{"skill": "list_trash", "arguments": {"q": "test3"}}, {"skill": "restore_item", '
        '"arguments": {"item_id": {"from": 0, "path": "items.0.id"}}}].\n'
        '  Example — "what is in the test folder": '
        '[{"skill": "search", "arguments": {"q": "test"}}, {"skill": "list_items", "arguments": '
        '{"parent_id": {"from": 0, "path": "items.0.id"}}}].\n'
        '  Example — "move the selected files into test2": '
        '[{"skill": "search", "arguments": {"q": "test2"}}, {"skill": "move_item", "arguments": '
        '{"item_id": {"from": "selection", "each": true}, '
        '"parent_id": {"from": 0, "path": "items.0.id"}}}].\n'
        '  Example — "delete everything in the test folder": '
        '[{"skill": "search", "arguments": {"q": "test"}}, {"skill": "list_items", "arguments": '
        '{"parent_id": {"from": 0, "path": "items.0.id"}}}, {"skill": "trash_item", "arguments": '
        '{"item_id": {"from": 1, "path": "items.*.id"}}}].\n'
        f"{followup_rule}"
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


# Arguments that must name a folder to put something *into*. Referencing a step
# that returns "the item I just changed" here is the mis-numbering signature
# described in _reference_problems.
_DESTINATION_ARGS = frozenset({"parent_id"})


def _path_head(path: str) -> str:
    """First segment of a reference path (``"items.0.id"`` → ``"items"``)."""

    return next(iter(part for part in path.split(".") if part), "")


def _reference_problems(
    *,
    index: int,
    arg_name: str,
    path: str,
    source: RegisteredSkill | None,
    from_step: int,
) -> list[str]:
    """Check a step reference against what the referenced skill actually returns.

    Two failures this catches, both observed on real runs and both previously
    only detectable at execution time — i.e. after any earlier write steps in
    the same plan had already taken effect:

    1. **Wrong path for the shape.** ``items.0.id`` against ``create_folder``
       (which returns the item itself) raises ``cannot resolve path`` mid-run.
    2. **A mutated item used as a destination.** ``{"parent_id": {"from": 3}}``
       where step 3 is a ``move_item`` — the destination becomes whatever that
       step moved, so the run dies on "Destination must be a folder". This is
       what a model that has lost track of its own step numbering produces.

    Both are reported as plan problems so the repair loop can fix them while
    nothing has run yet. Rule 2 does reject one legitimate-but-unusual plan
    ("move folder A into B, then move files into A"): the recovery is to
    reference the lookup that found A instead, which the repair message names.
    """

    if source is None or source.output is SkillOutput.OPAQUE:
        return []  # self-built skills declare no shape; do not guess one
    head = _path_head(path)
    field = path.rsplit(".", 1)[-1] or "id"
    problems: list[str] = []
    if source.output is SkillOutput.PAGED_ITEMS:
        if head != "items":
            problems.append(
                f"step {index}: argument '{arg_name}' references step {from_step} "
                f"('{source.name}') with path '{path}', but that step returns "
                f'{{"items": [...], "total": N}} — use "items.0.{field}"'
            )
    elif source.output is SkillOutput.ITEM_LIST:
        if not head.isdigit() and head != "*":
            problems.append(
                f"step {index}: argument '{arg_name}' references step {from_step} "
                f"('{source.name}') with path '{path}', but that step returns a plain "
                f'list — use "0.{field}"'
            )
    elif head in {"items", "*"} or head.isdigit():
        problems.append(
            f"step {index}: argument '{arg_name}' references step {from_step} "
            f"('{source.name}') with path '{path}', but that step returns the item "
            f'itself — use "{field}"'
        )
    if arg_name in _DESTINATION_ARGS and source.output is SkillOutput.MUTATED_ITEM:
        problems.append(
            f"step {index}: argument '{arg_name}' must be a folder, but it references "
            f"step {from_step} ('{source.name}'), which returns the item that step "
            "changed. Reference the step that created or found the destination folder."
        )
    return problems


def _repair_message(problems: list[str]) -> str:
    """What the planner is told after an invalid plan.

    Most problems name their own fix ('use "items.0.id"'), so the instruction is
    to apply exactly those and change nothing else. The escape hatch — "return
    an empty steps list" — is offered ONLY when a skill it wanted does not
    exist, because that is the one case where the request may genuinely be
    unsatisfiable. Offering it unconditionally taught the model to give up on a
    fixable reference: on a real multi-turn run it answered "please tick the
    files first" instead of correcting one step index.
    """

    unsatisfiable = any("unknown skill" in problem for problem in problems)
    tail = (
        " If a skill you need does not exist, return an empty steps list and explain "
        "briefly in reply."
        if unsatisfiable
        else " Apply exactly these corrections and keep the rest of the plan as it is. "
        "Do not ask the user to select files, and do not give up on a fixable step."
    )
    return "Your previous plan was invalid: " + "; ".join(problems) + "." + tail


def validate_plan(
    steps: list[PlannedStep],
    registry: SkillRegistry,
    *,
    preceding: list[PlannedStep] | None = None,
) -> list[str]:
    """Semantic validation of a planned workflow against the skill catalog.

    Catches the classes of failure a JSON-parse check misses: a hallucinated
    skill, a step that omits a required argument (e.g. ``search`` without
    ``q``), or a reference whose path cannot possibly resolve against what the
    referenced step returns. Returns a list of human-readable problems ([]
    means the plan is executable).

    ``preceding`` is the steps that already exist ahead of these ones — the
    second pass of two-phase planning continues an existing plan, so its first
    step is at index ``len(preceding)`` and it may legitimately reference any
    of them. They are passed (rather than just a count) so a reference into
    them is checked against their real output shape too.
    """

    earlier = list(preceding or [])
    index_offset = len(earlier)
    all_steps = [*earlier, *steps]
    problems: list[str] = []
    for position, step in enumerate(steps):
        index = position + index_offset
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
        for arg_name, arg_value in step.arguments.items():
            # Step-output references must point at an earlier step. Selection
            # references are always resolvable (the selection exists independently
            # of step order), so they are exempt from the earlier-step rule.
            if is_step_ref(arg_value):
                from_step = ref_source(arg_value)
                if not isinstance(from_step, int) or from_step < 0 or from_step >= index:
                    problems.append(
                        f"step {index}: reference must point to an earlier step, got {from_step}"
                    )
                    continue
                problems.extend(
                    _reference_problems(
                        index=index,
                        arg_name=arg_name,
                        path=str(arg_value.get("path", "")),
                        source=registry.get(all_steps[from_step].skill),
                        from_step=from_step,
                    )
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
        two_phase_planning: bool | None = None,
    ) -> None:
        self._llm = llm
        self._registry = registry
        self._context = context
        self._num_ctx = num_ctx
        self._max_repair = max(0, max_repair)
        # Must match WorkflowService's flag: the prompt may only teach the
        # split-plan rule when a second pass will actually run (see
        # build_planner_prompt). Injectable so tests skip global settings.
        self._two_phase_planning = (
            get_settings().assistant_two_phase_planning
            if two_phase_planning is None
            else two_phase_planning
        )
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
        preceding_steps: list[PlannedStep] | None = None,
    ) -> PlanResult:
        """``preceding_steps``: the steps that already exist when this call
        continues an existing plan (two-phase planning). The new steps start at
        index ``len(preceding_steps)``, and validation treats references back
        into them as legitimate — checking them against their real output shape
        rather than just their index."""

        selected = selected_items or []
        messages = [
            LLMMessage(
                role="system",
                content=build_planner_prompt(self._registry, two_phase=self._two_phase_planning),
            ),
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
        else:
            # Saying nothing let the model assume a selection existed and plan
            # {"from": "selection"} references, which the service can only answer
            # with "please tick the files first" — a dead end for a request that
            # named the files perfectly well. Observed on real multi-turn runs:
            # five of five ended there instead of searching for the files.
            messages.append(
                LLMMessage(
                    role="system",
                    content=(
                        "The user has NO files selected right now, so selection references "
                        '({"from": "selection", ...}) are unavailable — a plan using one '
                        "cannot run. Find the items you need with search or list_items and "
                        "reference those steps' output instead."
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
                failed = PlanResult(reply=response.content.strip() or last_reply)
                failed._set_llm_meta(response)
                return failed
            last_reply = result.reply or last_reply
            problems = validate_plan(result.steps, self._registry, preceding=preceding_steps)
            if not problems:
                result._set_llm_meta(response)
                return result
            if attempt < self._max_repair:
                messages.append(LLMMessage(role="assistant", content=response.content))
                messages.append(LLMMessage(role="user", content=_repair_message(problems)))

        # Repairs exhausted — never execute an invalid plan; answer conversationally.
        exhausted = PlanResult(
            reply=(
                last_reply
                if last_reply != "I could not plan that request."
                else "I couldn't turn that into a valid action with the tools I have. "
                "Could you rephrase or be more specific?"
            ),
            steps=[],
        )
        exhausted._set_llm_meta(response)
        return exhausted
