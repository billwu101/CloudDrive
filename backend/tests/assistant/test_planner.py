from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import (
    _PLAN_RESPONSE_FORMAT,
    PlanResult,
    WorkflowPlanner,
    _parse,
    build_plan_response_format,
    build_planner_prompt,
    validate_plan,
)
from app.assistant.skills.builtin import build_read_only_registry, register_write_skills
from app.assistant.skills.registry import RegisteredSkill, SkillOutput, SkillRegistry
from app.assistant.workflow import PlannedStep
from app.drive.service import DriveService
from app.search.service import SearchService
from app.trash.service import TrashService
from app.users.service import QuotaService


class ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]) -> None:
        self.responses = responses
        self.calls = 0
        self.response_formats: list[dict[str, Any] | None] = []
        self.disable_thinkings: list[bool | None] = []
        self.messages_seen: list[list[LLMMessage]] = []

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
        temperature: float | None = None,
        disable_thinking: bool | None = None,
    ) -> LLMResponse:
        self.calls += 1
        self.response_formats.append(response_format)
        self.disable_thinkings.append(disable_thinking)
        self.messages_seen.append(list(messages))
        return self.responses.pop(0)


def _registry() -> SkillRegistry:
    registry = SkillRegistry()

    async def handler(context, args):  # type: ignore[no-untyped-def]
        return {}

    registry.register(
        RegisteredSkill(
            name="list_items",
            description="List items.",
            parameters={"type": "object", "properties": {}, "additionalProperties": True},
            permission_tier="read",
            handler=handler,
        )
    )
    registry.register(
        RegisteredSkill(
            name="search",
            description="Search by name.",
            parameters={
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
                "additionalProperties": True,
            },
            permission_tier="read",
            handler=handler,
        )
    )
    return registry


def _planner(
    llm: ScriptedLLM, *, max_repair: int = 2, disable_thinking: bool | None = True
) -> WorkflowPlanner:
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=3,
        privacy_default="non_sensitive",
    )
    return WorkflowPlanner(
        llm=router,
        registry=_registry(),
        context=ContextManager(num_ctx=2048),
        num_ctx=2048,
        max_repair=max_repair,
        disable_thinking=disable_thinking,
    )


async def test_planner_disables_thinking_on_every_call() -> None:
    # DEC-033: the planner runs with Ollama's thinking phase off (E8 — cured
    # repetition loops, ~10x faster). The flag must reach the LLM client on every
    # plan call, including repair retries.
    llm = ScriptedLLM(
        [
            LLMResponse(content='{"reply": "", "steps": [{"skill": "search"}]}'),
            LLMResponse(
                content='{"reply": "ok", "steps": [{"skill": "search", "arguments": {"q": "x"}}]}'
            ),
        ]
    )
    await _planner(llm).plan(message="find x")
    assert llm.disable_thinkings == [True, True]


async def test_planner_threads_history_between_system_and_current_message() -> None:
    # Conversation memory: prior turns must land after the system framing and
    # before the current user message, so references resolve against context.
    llm = ScriptedLLM([LLMResponse(content='{"reply": "ok", "steps": []}')])
    history = [
        LLMMessage(role="user", content="list Reports"),
        LLMMessage(role="assistant", content="[executed] list_items: ok → budget.xlsx"),
    ]
    await _planner(llm).plan(message="rename the first one", history=history)
    seen = llm.messages_seen[0]
    assert seen[0].role == "system"
    non_system = [m for m in seen if m.role != "system"]
    assert non_system == [*history, LLMMessage(role="user", content="rename the first one")]


async def test_planner_without_history_is_single_turn() -> None:
    llm = ScriptedLLM([LLMResponse(content='{"reply": "ok", "steps": []}')])
    await _planner(llm).plan(message="hi")
    non_system = [m for m in llm.messages_seen[0] if m.role != "system"]
    assert non_system == [LLMMessage(role="user", content="hi")]


async def test_planner_parses_plain_json() -> None:
    llm = ScriptedLLM([LLMResponse(content='{"reply": "ok", "steps": [{"skill": "list_items"}]}')])
    result = await _planner(llm).plan(message="show files")
    assert result.reply == "ok"
    assert result.steps[0].skill == "list_items"
    # A valid first plan must not trigger the repair loop — exactly one LLM call.
    assert llm.calls == 1


async def test_planner_requests_structured_output_on_every_call() -> None:
    # The plan schema must reach the LLM client so providers can enforce it with
    # constrained decoding (Ollama format / OpenAI json_schema). DEC-032: the
    # schema constrains `skill` to the registry's real names (sorted), so a
    # hallucinated skill is unrepresentable at sampling time.
    llm = ScriptedLLM([LLMResponse(content='{"reply": "ok", "steps": []}')])
    await _planner(llm).plan(message="hi")
    assert len(llm.response_formats) == 1
    sent = cast(dict[str, Any], llm.response_formats[0])
    step_props = sent["json_schema"]["schema"]["properties"]["steps"]["items"]["properties"]
    assert step_props["skill"]["enum"] == ["list_items", "search"]


def test_plan_response_format_enum_matches_registry() -> None:
    # DEC-032 round-trip: enum == sorted registry names; an empty registry must
    # fall back to a free string (an empty enum is invalid JSON Schema).
    sent = cast(dict[str, Any], build_plan_response_format(_registry()))
    step_props = sent["json_schema"]["schema"]["properties"]["steps"]["items"]["properties"]
    assert step_props["skill"] == {"type": "string", "enum": ["list_items", "search"]}

    empty = cast(dict[str, Any], build_plan_response_format(SkillRegistry()))
    empty_props = empty["json_schema"]["schema"]["properties"]["steps"]["items"]["properties"]
    assert empty_props["skill"] == {"type": "string"}


def test_plan_response_format_stays_in_sync_with_models() -> None:
    # _PLAN_RESPONSE_FORMAT is hand-written (deliberately: the Pydantic models
    # have defaults, so model_json_schema() would emit no `required` and weaken
    # constrained decoding). This drift test fails if the models gain/lose/rename
    # fields without the schema being updated to match.
    json_schema = cast(dict[str, Any], _PLAN_RESPONSE_FORMAT["json_schema"])
    plan_schema = json_schema["schema"]
    assert set(plan_schema["properties"]) == set(PlanResult.model_fields)
    assert set(plan_schema["required"]) == set(PlanResult.model_fields)

    step_schema = plan_schema["properties"]["steps"]["items"]
    assert set(step_schema["properties"]) == set(PlannedStep.model_fields)
    assert set(step_schema["required"]) == set(PlannedStep.model_fields)


async def test_plan_result_exposes_llm_diagnostics() -> None:
    # done_reason/token counts come from the LLMResponse, not the model's JSON
    # content — PlanResult surfaces them via PrivateAttr (not a public field,
    # see test_plan_response_format_stays_in_sync_with_models above) so the
    # service layer can populate AssistantChatResponse.llm_meta.
    response = LLMResponse(
        content='{"reply": "ok", "steps": []}',
        done_reason="stop",
        prompt_tokens=42,
        completion_tokens=7,
    )
    result = await _planner(ScriptedLLM([response])).plan(message="hi")
    assert result.done_reason == "stop"
    assert result.prompt_tokens == 42
    assert result.completion_tokens == 7
    # Not part of the model's own output schema.
    assert "done_reason" not in PlanResult.model_fields


async def test_plan_result_llm_diagnostics_on_invalid_json() -> None:
    # Even when parsing fails and the fallback PlanResult is built directly
    # (not via _parse), diagnostics must still be attached. Invalid JSON trips
    # ModelRouter's own local-retry loop (max_local_attempts=3 in _planner());
    # target="local" makes it return the last unvalidated response instead of
    # falling through to (disabled) external, and needs 3 identical responses.
    response = LLMResponse(content="not json at all", done_reason="length", prompt_tokens=10)
    result = await _planner(ScriptedLLM([response, response, response]), max_repair=0).plan(
        message="hi", target="local"
    )
    assert result.done_reason == "length"
    assert result.prompt_tokens == 10


async def test_planner_strips_code_fences() -> None:
    content = '```json\n{"reply": "ok", "steps": []}\n```'
    result = await _planner(ScriptedLLM([LLMResponse(content=content)])).plan(message="hi")
    assert result.reply == "ok"
    assert result.steps == []


async def test_planner_repairs_invalid_json_with_retry() -> None:
    llm = ScriptedLLM(
        [
            LLMResponse(content="not json at all"),
            LLMResponse(content='{"reply": "fixed", "steps": []}'),
        ]
    )
    result = await _planner(llm).plan(message="hi")
    assert result.reply == "fixed"
    assert llm.calls == 2


def test_validate_plan_flags_unknown_skill_and_missing_required_arg() -> None:
    registry = _registry()
    problems = validate_plan(
        [
            PlannedStep(skill="search", arguments={}),  # missing required q
            PlannedStep(skill="rm_rf", arguments={}),  # unknown skill
        ],
        registry,
    )
    assert any("missing required argument 'q'" in p for p in problems)
    assert any("unknown skill 'rm_rf'" in p for p in problems)


def test_validate_plan_accepts_complete_plan() -> None:
    problems = validate_plan([PlannedStep(skill="search", arguments={"q": "test"})], _registry())
    assert problems == []


def test_validate_plan_flags_invalid_depends_on() -> None:
    # Mirrors classify_steps' rule so a bad depends_on triggers the planner's
    # repair loop instead of a 400 from the permission layer (real gemma emitted
    # a self-dependency: "Step 0 has an invalid dependency: 0").
    self_dep = validate_plan(
        [PlannedStep(skill="search", arguments={"q": "x"}, depends_on=[0])], _registry()
    )
    assert any("depends_on must point to an earlier step, got 0" in p for p in self_dep)

    forward = validate_plan(
        [
            PlannedStep(skill="search", arguments={"q": "x"}, depends_on=[]),
            PlannedStep(skill="list_items", arguments={}, depends_on=[2]),
        ],
        _registry(),
    )
    assert any("depends_on must point to an earlier step, got 2" in p for p in forward)

    valid = validate_plan(
        [
            PlannedStep(skill="search", arguments={"q": "x"}),
            PlannedStep(skill="list_items", arguments={}, depends_on=[0]),
        ],
        _registry(),
    )
    assert valid == []


def test_validate_plan_accepts_step_reference_for_required_arg() -> None:
    # list_items.parent_id is satisfied by a reference to step 0's output.
    steps = [
        PlannedStep(skill="search", arguments={"q": "test"}),
        PlannedStep(
            skill="list_items",
            arguments={"parent_id": {"from_step": 0, "path": "items.0.id"}},
        ),
    ]
    assert validate_plan(steps, _registry()) == []


def test_validate_plan_rejects_forward_reference() -> None:
    steps = [
        PlannedStep(
            skill="list_items",
            arguments={"parent_id": {"from_step": 1, "path": "items.0.id"}},
        ),
        PlannedStep(skill="search", arguments={"q": "test"}),
    ]
    problems = validate_plan(steps, _registry())
    assert any("must point to an earlier step" in p for p in problems)


async def test_planner_repairs_missing_required_argument() -> None:
    # First plan calls search without q (parses as JSON, but invalid) -> repair ->
    # second plan supplies q. The bad plan must never reach execution.
    llm = ScriptedLLM(
        [
            LLMResponse(content='{"reply": "searching", "steps": [{"skill": "search"}]}'),
            LLMResponse(
                content='{"reply": "searching test", "steps":'
                ' [{"skill": "search", "arguments": {"q": "test"}}]}'
            ),
        ]
    )
    result = await _planner(llm).plan(message="what is in the test folder")
    assert llm.calls == 2
    assert [s.skill for s in result.steps] == ["search"]
    assert result.steps[0].arguments == {"q": "test"}


async def test_planner_gives_up_gracefully_without_executing_invalid_plan() -> None:
    # Model keeps emitting an invalid plan; after repairs are exhausted the planner
    # must return NO steps (so nothing executes) rather than a broken call.
    bad = LLMResponse(content='{"reply": "I will search", "steps": [{"skill": "search"}]}')
    llm = ScriptedLLM([bad, bad, bad, bad])
    result = await _planner(llm, max_repair=2).plan(message="what is in the test folder")
    assert result.steps == []  # nothing to execute → no "missing argument" failure
    assert result.reply  # has a conversational explanation
    assert llm.calls == 3  # initial + 2 repairs


def test_planner_prompt_documents_each_step_output_shape() -> None:
    """The planner must be told what each skill returns, not just search/list_items.

    2026-07-28: an eval case (gen-ec2-101, "sort these files into folders by
    name") failed live with `move_item: argument 'parent_id': cannot resolve
    path 'items.0.id' from step 1` — the model referenced a folder it had just
    created as if create_folder returned {"items": [...]}. The prompt only ever
    documented the paged shape and every example used items.0.id, so that was
    the only shape it had seen. Verified against the real implementations in
    skills/builtin/{read_only,write}.py.
    """

    async def handler(context, args):  # type: ignore[no-untyped-def]
        return {}

    registry = SkillRegistry()
    registry.register(
        RegisteredSkill(
            name="create_folder",
            description="Create a folder.",
            parameters={"type": "object", "properties": {}},
            permission_tier="write",
            handler=handler,
        )
    )
    prompt = build_planner_prompt(registry)

    # The paged shape (unchanged) and the two shapes that were missing.
    assert '"items": [{"id", "name", "item_type", ...}], "total": N' in prompt
    assert "recent returns a plain list of items" in prompt
    assert "return the ITEM ITSELF" in prompt
    # And the concrete correction for the observed failure.
    assert '{"parent_id": {"from": 1, "path": "id"}}' in prompt


def test_split_plan_rule_is_only_taught_when_a_second_pass_will_run() -> None:
    """Teaching needs_followup with two-phase planning off makes the model return
    read-only lookups and stop — the writes it deferred never get planned. On 20
    EC2 cases against the real model that was 0/20 (every failure: the write step
    missing) versus 7/20 with the second pass actually running.
    """

    async def handler(context: object, args: object) -> object:  # pragma: no cover
        return None

    registry = SkillRegistry()
    registry.register(
        RegisteredSkill(
            name="create_folder",
            description="Create a folder.",
            parameters={"type": "object", "properties": {}},
            permission_tier="write",
            handler=handler,
        )
    )

    on = build_planner_prompt(registry, two_phase=True)
    off = build_planner_prompt(registry, two_phase=False)

    assert "set it to true ONLY when you cannot tell which items" in on
    assert "set it to true ONLY when you cannot tell which items" not in off
    assert "needs_followup: always false" in off
    assert "including every write step" in off


def _shape_registry() -> SkillRegistry:
    """A registry mirroring the real skills' declared output shapes."""

    async def handler(context: object, args: object) -> object:  # pragma: no cover
        return None

    registry = SkillRegistry()
    for name, tier, output in (
        ("search", "read", SkillOutput.PAGED_ITEMS),
        ("recent", "read", SkillOutput.ITEM_LIST),
        ("get_info", "read", SkillOutput.ITEM),
        ("create_folder", "write", SkillOutput.NEW_FOLDER),
        ("rename_item", "write", SkillOutput.MUTATED_ITEM),
        ("move_item", "write", SkillOutput.MUTATED_ITEM),
        ("my_own_skill", "write", SkillOutput.OPAQUE),
    ):
        registry.register(
            RegisteredSkill(
                name=name,
                description=name,
                parameters={"type": "object", "properties": {}},
                permission_tier=tier,
                handler=handler,
                output=output,
            )
        )
    return registry


def _search_step() -> PlannedStep:
    """A preceding search whose output a write step can legitimately reference."""

    return PlannedStep(skill="search", arguments={"q": "報告"}, depends_on=[])


def test_paged_path_against_a_step_that_returns_the_item_itself_is_rejected() -> None:
    """The exact failure `cannot resolve path 'items.0.id' from step 0` — until
    now only observable at execution time, i.e. after step 0 had already run."""

    steps = [
        PlannedStep(skill="create_folder", arguments={"name": "Reports"}, depends_on=[]),
        PlannedStep(
            skill="move_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}},
            depends_on=[0],
        ),
    ]

    problems = validate_plan(steps, _shape_registry())

    assert len(problems) == 1
    assert "returns the item itself" in problems[0]
    assert 'use "id"' in problems[0]


def test_item_path_against_a_paged_step_is_rejected() -> None:
    steps = [
        PlannedStep(skill="search", arguments={"q": "報告"}, depends_on=[]),
        PlannedStep(
            skill="move_item", arguments={"item_id": {"from": 0, "path": "id"}}, depends_on=[0]
        ),
    ]

    problems = validate_plan(steps, _shape_registry())

    assert len(problems) == 1
    assert 'use "items.0.id"' in problems[0]


def test_recent_needs_a_bare_index_not_an_items_prefix() -> None:
    steps = [
        PlannedStep(skill="recent", arguments={}, depends_on=[]),
        PlannedStep(
            skill="move_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}},
            depends_on=[0],
        ),
    ]

    problems = validate_plan(steps, _shape_registry())

    assert len(problems) == 1
    assert 'use "0.id"' in problems[0]


def test_correct_paths_for_each_shape_pass() -> None:
    steps = [
        PlannedStep(skill="search", arguments={"q": "報告"}, depends_on=[]),
        PlannedStep(skill="recent", arguments={}, depends_on=[]),
        PlannedStep(skill="create_folder", arguments={"name": "Reports"}, depends_on=[]),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": 0, "path": "items.*.id"},
                "parent_id": {"from": 2, "path": "id"},
            },
            depends_on=[0, 2],
        ),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": 1, "path": "0.id"},
                "parent_id": {"from": 2, "path": "id"},
            },
            depends_on=[1, 2],
        ),
    ]

    assert validate_plan(steps, _shape_registry()) == []


def test_a_destination_may_not_be_the_item_another_step_just_moved() -> None:
    """Observed on a real run: the model lost track of its own numbering and
    pointed parent_id at a move_item, so the destination became the file that
    step had moved. It failed at execution with "Destination must be a folder"
    — after two of the four moves had already happened."""

    steps = [
        PlannedStep(skill="search", arguments={"q": "發票"}, depends_on=[]),
        PlannedStep(skill="create_folder", arguments={"name": "發票"}, depends_on=[]),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": 0, "path": "items.0.id"},
                "parent_id": {"from": 1, "path": "id"},
            },
            depends_on=[0, 1],
        ),
        PlannedStep(
            skill="move_item",
            arguments={
                "item_id": {"from": 0, "path": "items.1.id"},
                "parent_id": {"from": 2, "path": "id"},  # step 2 is a move, not the folder
            },
            depends_on=[0, 2],
        ),
    ]

    problems = validate_plan(steps, _shape_registry())

    assert len(problems) == 1
    assert "must be a folder" in problems[0]
    assert "created or found the destination folder" in problems[0]


def test_self_built_skills_declare_no_shape_and_are_not_second_guessed() -> None:
    steps = [
        PlannedStep(skill="my_own_skill", arguments={}, depends_on=[]),
        PlannedStep(
            skill="move_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}},
            depends_on=[0],
        ),
    ]

    assert validate_plan(steps, _shape_registry()) == []


def test_references_into_the_first_pass_are_shape_checked_too() -> None:
    """Two-phase planning validates the second pass alone. Passing the earlier
    steps (not just how many there are) is what lets a reference back into them
    be checked against what they actually return."""

    preceding = [PlannedStep(skill="create_folder", arguments={"name": "發票"}, depends_on=[])]
    second_pass = [
        PlannedStep(
            skill="move_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}},
            depends_on=[0],
        )
    ]

    problems = validate_plan(second_pass, _shape_registry(), preceding=preceding)

    assert len(problems) == 1
    assert "returns the item itself" in problems[0]
    # The step numbering still accounts for the first pass.
    assert problems[0].startswith("step 1:")


def test_prompt_output_shapes_match_what_the_skills_declare() -> None:
    """The prompt names the shapes in prose; ``validate_plan`` enforces them from
    ``RegisteredSkill.output``. Two sources of truth for one fact — this test is
    what keeps them from drifting apart (a skill whose declared shape contradicts
    the prompt would have the model taught one thing and validated against
    another).
    """

    registry = build_read_only_registry(
        drive_service=AsyncMock(spec=DriveService),
        search_service=AsyncMock(spec=SearchService),
        quota_service=AsyncMock(spec=QuotaService),
        trash_service=AsyncMock(spec=TrashService),
    )
    register_write_skills(
        registry,
        drive_service=AsyncMock(spec=DriveService),
        trash_service=AsyncMock(spec=TrashService),
    )
    prompt = build_planner_prompt(registry)
    paged_line, list_line, item_line = (
        next(line for line in prompt.splitlines() if marker in line)
        for marker in ('"total": N', "plain list of items", "return the ITEM ITSELF")
    )
    expected_line = {
        SkillOutput.PAGED_ITEMS: paged_line,
        SkillOutput.ITEM_LIST: list_line,
        SkillOutput.ITEM: item_line,
        SkillOutput.NEW_FOLDER: item_line,
        SkillOutput.MUTATED_ITEM: item_line,
    }
    for skill in registry.list_skills():
        if skill.output is SkillOutput.OPAQUE:
            continue  # not usable as a reference source; the prompt says nothing
        assert skill.name in expected_line[skill.output], (
            f"{skill.name} declares {skill.output} but the prompt does not list it there"
        )


def test_chat_template_debris_is_stripped_from_plan_arguments() -> None:
    """Reproduced 4/5 against the OpenAI-compatible gateway (gemma4:26b): asking
    for a folder named AgentFolder_23f4b9ba planned
    ``AgentFolder_23f4b9ba'}}]}<tool_call|>> {`` — and the folder was CREATED
    under that name, because the surrounding JSON parsed cleanly. The same
    prompts against local Ollama never did it, so this is the gateway's decoding
    path leaking chat-template tokens into a string value.
    """

    raw = (
        '{"reply": "ok", "needs_followup": false, "steps": [{"skill": "create_folder", '
        '"arguments": {"name": "AgentFolder_23f4b9ba\'}}]}<tool_call|>> {"}, '
        '"depends_on": []}]}'
    )

    result = _parse(raw)

    assert result is not None
    assert result.steps[0].arguments == {"name": "AgentFolder_23f4b9ba"}


def test_a_clean_plan_is_left_exactly_as_it_is() -> None:
    raw = (
        '{"reply": "ok", "needs_followup": false, "steps": [{"skill": "create_folder", '
        '"arguments": {"name": "Reports <2026> [final]"}, "depends_on": []}]}'
    )

    result = _parse(raw)

    assert result is not None
    # Angle brackets and braces are legal in a name; only template tokens count.
    assert result.steps[0].arguments == {"name": "Reports <2026> [final]"}


def test_debris_in_the_reply_text_is_stripped_too() -> None:
    raw = '{"reply": "已建立資料夾。<end_of_turn>", "needs_followup": false, "steps": []}'

    result = _parse(raw)

    assert result is not None
    assert result.reply == "已建立資料夾。"


def test_debris_without_a_template_token_is_stripped_too() -> None:
    """A second observed shape: the model closed the JSON inside the string and
    then simply carried on talking. No template token to key on — the signature
    is the quote-plus-closing-brackets run."""

    raw = (
        '{"reply": "ok", "needs_followup": false, "steps": [{"skill": "create_folder", '
        '"arguments": {"name": "AgentFolder_90e16c4f\'}}]}of course! Here is your plan:{"}, '
        '"depends_on": []}]}'
    )

    result = _parse(raw)

    assert result is not None
    assert result.steps[0].arguments == {"name": "AgentFolder_90e16c4f"}


def test_a_name_with_ordinary_brackets_survives() -> None:
    raw = (
        '{"reply": "ok", "needs_followup": false, "steps": [{"skill": "create_folder", '
        '"arguments": {"name": "report [2026] {final}"}, "depends_on": []}]}'
    )

    result = _parse(raw)

    assert result is not None
    assert result.steps[0].arguments == {"name": "report [2026] {final}"}


def test_a_byte_token_in_an_argument_is_rejected_not_repaired_by_guessing() -> None:
    """報告_2026 arrived from the model as 報告_20<0xA0>26 and the folder was
    created under that name. Deleting the marker would be a guess: it happens to
    give the right answer here, but 預算_20<0xA0>6 → 預算_206 is a different
    year. Rejection sends it back through the repair loop instead.
    """

    steps = [
        PlannedStep(
            skill="rename_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}, "new_name": "報告_20<0xA0>26"},
            depends_on=[0],
        )
    ]

    problems = validate_plan(steps, _shape_registry(), preceding=[_search_step()])

    assert len(problems) == 1
    assert "raw byte tokens" in problems[0]
    assert "new_name" in problems[0]


def test_clean_arguments_are_untouched_by_the_byte_token_rule() -> None:
    steps = [
        PlannedStep(
            skill="rename_item",
            arguments={"item_id": {"from": 0, "path": "items.0.id"}, "new_name": "報告_2026"},
            depends_on=[0],
        )
    ]

    assert validate_plan(steps, _shape_registry(), preceding=[_search_step()]) == []


def test_byte_tokens_are_only_scrubbed_from_the_reply_text() -> None:
    """Prose with <0xA0> in it is merely ugly, so it gets cleaned. The same
    marker in an argument must survive parsing so validate_plan can reject it."""

    raw = (
        '{"reply": "已建立 報告_20<0xA0>26。", "needs_followup": false, "steps": '
        '[{"skill": "create_folder", "arguments": {"name": "報告_20<0xA0>26"}, "depends_on": []}]}'
    )

    result = _parse(raw)

    assert result is not None
    assert result.reply == "已建立 報告_2026。"
    assert result.steps[0].arguments == {"name": "報告_20<0xA0>26"}
