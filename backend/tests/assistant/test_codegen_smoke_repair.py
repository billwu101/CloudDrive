"""Generated code must run once before the user is asked to approve it.

18 of 100 generated skills in the 2026-07-29 full eval raised on their very
first call — ``NameError: name 'outputode_dir' is not defined`` and similar
token garbling. Every one passed the AST safety scan and the manifest schema,
because neither executes anything. The user found out after approving and
installing.
"""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.sandbox import SkillSandbox
from app.assistant.skills.smoke import smoke_test_generated_code
from app.assistant.subagent import CodegenSubAgent

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="sandbox relies on POSIX process groups"
)

_BROKEN = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    with open(os.path.join(outputode_dir, 'out.txt'), 'w') as fh:\n"
    "        fh.write('hi')\n"
    "    return {'ok': True}\n"
)
_WORKING = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    with open(os.path.join(output_dir, 'out.txt'), 'w') as fh:\n"
    "        fh.write('hi')\n"
    "    return {'ok': True}\n"
)
# Needs a PNG; the smoke fixture is plain text. Not the code's fault.
_IMAGE_SKILL = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    data = open(input_path, 'rb').read()\n"
    "    if not data.startswith(b'\\x89PNG'):\n"
    "        raise ValueError('not a PNG image')\n"
    "    return {'ok': True}\n"
)


def _payload(code: str, name: str = "write_note") -> str:
    return json.dumps(
        {
            "name": name,
            "description": "Write a note.",
            "code": code,
            "ui": {
                "context_menu": [{"label": "Write note", "handler": name, "item_types": ["FILE"]}]
            },
        }
    )


class ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self.calls = 0
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
        self.messages_seen.append(list(messages))
        return LLMResponse(content=self._responses[min(self.calls - 1, len(self._responses) - 1)])


def _agent(llm: ScriptedLLM) -> CodegenSubAgent:
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    return CodegenSubAgent(llm=router, context=ContextManager(num_ctx=4096), num_ctx=4096)


def _smoke(code: str, item_types: list[str]) -> Any:
    return smoke_test_generated_code(SkillSandbox(timeout_sec=20), code, item_types)


async def test_code_that_dies_on_first_run_is_sent_back_for_repair() -> None:
    llm = ScriptedLLM([_payload(_BROKEN), _payload(_WORKING)])

    result = await _agent(llm).author(request="做一個寫筆記的功能", smoke=_smoke)

    assert llm.calls == 2  # the first draft was rejected by actually running it
    assert result.ok
    assert "output_dir" in result.code and "outputode_dir" not in result.code
    # The repair prompt carried the real traceback, not a generic complaint.
    repair = llm.messages_seen[1][-1].content
    assert "NameError" in repair


async def test_a_working_skill_is_accepted_without_a_second_call() -> None:
    llm = ScriptedLLM([_payload(_WORKING)])

    result = await _agent(llm).author(request="做一個寫筆記的功能", smoke=_smoke)

    assert llm.calls == 1
    assert result.ok


async def test_an_input_mismatch_is_not_treated_as_a_defect() -> None:
    """A PNG skill handed the text fixture fails — that says nothing about the
    code. The eval harness made exactly this mistake and spent 48 of 99 M4
    failures on it; repairing against a phantom problem is worse than not
    checking at all."""

    llm = ScriptedLLM([_payload(_IMAGE_SKILL, name="shrink_image")])

    result = await _agent(llm).author(request="做一個縮圖功能", smoke=_smoke)

    assert llm.calls == 1  # accepted, no repair round
    assert result.ok


async def test_smoke_is_optional_so_nothing_changes_without_a_sandbox() -> None:
    llm = ScriptedLLM([_payload(_BROKEN)])

    result = await _agent(llm).author(request="做一個寫筆記的功能")

    assert llm.calls == 1
    assert result.ok  # unchanged behaviour: broken code still gets proposed


def test_smoke_runs_every_declared_item_type() -> None:
    folder_only_break = (
        "import os\n"
        "def run(input_path, output_dir, params):\n"
        "    if os.path.isdir(input_path):\n"
        "        return {'n': undefined_name}\n"
        "    return {'ok': True}\n"
    )

    outcome = smoke_test_generated_code(
        SkillSandbox(timeout_sec=20), folder_only_break, ["FILE", "FOLDER"]
    )

    assert not outcome.ok
    assert outcome.is_code_defect
    assert "FOLDER" in outcome.error
