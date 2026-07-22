from __future__ import annotations

import json
from typing import Any

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.subagent import CodegenSubAgent

_GOOD_CODE = (
    "import zipfile\n"
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    with zipfile.ZipFile(input_path) as z:\n"
    "        z.extractall(output_dir)\n"
    "    return {'files': os.listdir(output_dir)}\n"
)


def _proposal(name: str = "decompress_zip", code: str = _GOOD_CODE) -> dict[str, object]:
    return {
        "name": name,
        "description": "Extract a zip archive.",
        "version": "1.0.0",
        "code": code,
        "ui": {"context_menu": [{"label": "Extract", "handler": name, "item_types": ["FILE"]}]},
    }


class _ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._i = 0
        self.response_formats: list[dict[str, Any] | None] = []
        self.temperatures: list[float | None] = []
        self.disable_thinkings: list[bool | None] = []

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
        self.response_formats.append(response_format)
        self.temperatures.append(temperature)
        self.disable_thinkings.append(disable_thinking)
        item = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return LLMResponse(content=item)


def _agent(responses: list[str], *, max_repair: int = 2) -> CodegenSubAgent:
    router = ModelRouter(
        local_client=_ScriptedLLM(responses),
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    return CodegenSubAgent(
        llm=router, context=ContextManager(num_ctx=4096), num_ctx=4096, max_repair=max_repair
    )


async def test_author_requests_structured_output() -> None:
    # Codegen must carry the skill-proposal json_schema so constrained decoding
    # guarantees the {name, description, version, code, ui} envelope (same
    # mechanism as the planner's plan schema, DEC-031/032).
    llm = _ScriptedLLM([json.dumps(_proposal())])
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    agent = CodegenSubAgent(
        llm=router,
        context=ContextManager(num_ctx=4096),
        num_ctx=4096,
        max_repair=0,
        temperature=0.8,
        disable_thinking=True,
    )

    await agent.author(request="make a zip extractor")

    assert len(llm.response_formats) == 1
    sent = llm.response_formats[0]
    assert sent is not None
    schema = sent["json_schema"]["schema"]
    assert set(schema["required"]) == {"name", "description", "version", "code", "ui"}
    assert schema["properties"]["code"] == {"type": "string"}
    # Codegen must override the structured-temperature pin: 0.2 breaks code
    # generation (baseline at full sampling authored valid skills — proposal §7).
    assert llm.temperatures == [0.8]
    # DEC-034: codegen disables thinking (think:false) like the planner —
    # thinking-on codegen falls into repetition loops on gemma4:26b (real A/B
    # 0/6 → 6/6), overturning DEC-033's "codegen validated with thinking on".
    assert llm.disable_thinkings == [True]


async def test_author_disables_thinking_on_every_call() -> None:
    # DEC-034: every codegen call, including repair retries, must send think:false.
    llm = _ScriptedLLM(["not a json object", json.dumps(_proposal())])
    router = ModelRouter(
        local_client=llm,
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    agent = CodegenSubAgent(
        llm=router,
        context=ContextManager(num_ctx=4096),
        num_ctx=4096,
        max_repair=1,
        disable_thinking=True,
    )

    result = await agent.author(request="make a zip extractor")

    assert result.ok
    assert llm.disable_thinkings == [True, True]


async def test_author_returns_validated_proposal() -> None:
    agent = _agent([json.dumps(_proposal())])

    result = await agent.author(request="make a zip extractor")

    assert result.ok is True
    assert result.name == "decompress_zip"
    assert result.manifest is not None
    assert result.manifest["ui"]["context_menu"][0]["handler"] == "decompress_zip"
    assert "def run(" in result.code


async def test_author_repairs_after_unsafe_code() -> None:
    # First attempt uses subprocess (rejected by codeguard); second is clean.
    bad = _proposal(
        code="import subprocess\ndef run(input_path, output_dir, params):\n    return {}\n"
    )
    agent = _agent([json.dumps(bad), json.dumps(_proposal())])

    result = await agent.author(request="extract zip")

    assert result.ok is True
    assert result.name == "decompress_zip"


async def test_author_gives_up_with_problems_not_unsafe_code() -> None:
    bad = _proposal(code="import socket\ndef run(input_path, output_dir, params):\n    return {}\n")
    agent = _agent([json.dumps(bad)], max_repair=1)

    result = await agent.author(request="exfiltrate")

    assert result.ok is False
    assert result.code == ""  # never hands back code it could not validate
    assert any("socket" in p for p in result.problems)


async def test_author_normalizes_handler_to_skill_name() -> None:
    # handler must equal the skill name — a derived field, so a model slip
    # (observed live: 'seven_script_extract' vs 'seven_zip_extract') is fixed
    # mechanically instead of burning a repair round or failing the proposal.
    bad = _proposal()
    bad["ui"] = {
        "context_menu": [{"label": "x", "handler": "something_else", "item_types": ["FILE"]}]
    }
    agent = _agent([json.dumps(bad)], max_repair=0)

    result = await agent.author(request="zip")

    assert result.ok is True
    assert result.manifest is not None
    assert result.manifest["ui"]["context_menu"][0]["handler"] == result.name


async def test_author_handles_non_json_response() -> None:
    agent = _agent(["I'm not sure how to do that."], max_repair=0)

    result = await agent.author(request="???")

    assert result.ok is False
    assert result.problems
