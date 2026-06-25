from __future__ import annotations

import json

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

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
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


async def test_author_rejects_handler_name_mismatch() -> None:
    bad = _proposal()
    bad["ui"] = {
        "context_menu": [{"label": "x", "handler": "something_else", "item_types": ["FILE"]}]
    }
    agent = _agent([json.dumps(bad)], max_repair=0)

    result = await agent.author(request="zip")

    assert result.ok is False
    assert any("manifest" in p for p in result.problems)


async def test_author_handles_non_json_response() -> None:
    agent = _agent(["I'm not sure how to do that."], max_repair=0)

    result = await agent.author(request="???")

    assert result.ok is False
    assert result.problems
