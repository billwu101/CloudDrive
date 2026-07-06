from __future__ import annotations

import json

import httpx

from app.assistant.llm.client import LLMMessage
from app.assistant.llm.ollama import OllamaLLMClient

# The cross-provider shape planner sends (OpenAI json_schema envelope). Ollama's
# `format` parameter only understands the bare inner schema.
_ENVELOPE_FORMAT: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "workflow_plan",
        "schema": {
            "type": "object",
            "properties": {"reply": {"type": "string"}},
            "required": ["reply"],
        },
    },
}


def _capturing_client(captured: dict[str, object]) -> OllamaLLMClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message": {"content": "{}"}})

    return OllamaLLMClient(
        base_url="http://ollama.test",
        model="gemma4:26b",
        transport=httpx.MockTransport(handler),
    )


async def test_ollama_client_passes_bare_schema_as_format() -> None:
    # Constrained decoding: the schema inside the envelope must reach Ollama's
    # `format` verbatim — not the envelope itself, and not the weak "json" string.
    captured: dict[str, object] = {}
    client = _capturing_client(captured)

    await client.chat(
        [LLMMessage(role="user", content="plan it")],
        [],
        num_ctx=4096,
        response_format=_ENVELOPE_FORMAT,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    json_schema = _ENVELOPE_FORMAT["json_schema"]
    assert isinstance(json_schema, dict)
    assert payload["format"] == json_schema["schema"]
    # Structured output requests pin sampling for reproducible plans.
    assert payload["options"]["temperature"] == 0


async def test_ollama_client_passes_bare_schema_dict_through() -> None:
    # A caller may already hold a bare JSON Schema; it must pass through untouched.
    captured: dict[str, object] = {}
    client = _capturing_client(captured)
    bare_schema = {"type": "object", "properties": {"a": {"type": "integer"}}}

    await client.chat(
        [LLMMessage(role="user", content="plan it")],
        [],
        num_ctx=4096,
        response_format=bare_schema,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["format"] == bare_schema


async def test_ollama_client_omits_format_and_temperature_for_plain_chat() -> None:
    # Conversational calls (no response_format) must stay unconstrained and keep
    # default sampling — locking temperature globally would flatten chat replies.
    captured: dict[str, object] = {}
    client = _capturing_client(captured)

    await client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=4096)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "format" not in payload
    assert "temperature" not in payload["options"]


async def test_ollama_client_sends_gemma_runtime_options() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message": {"content": "ok"}})

    client = OllamaLLMClient(
        base_url="http://ollama.test",
        model="gemma4:26b",
        timeout=300,
        api_key="ollama-local",
        keep_alive="15m",
        transport=httpx.MockTransport(handler),
    )

    response = await client.chat(
        [LLMMessage(role="user", content="hello")],
        [],
        num_ctx=65536,
    )

    assert response.content == "ok"
    assert captured["authorization"] == "Bearer ollama-local"
    assert captured["payload"] == {
        "model": "gemma4:26b",
        "messages": [{"role": "user", "content": "hello"}],
        "stream": False,
        "options": {"num_ctx": 65536},
        "keep_alive": "15m",
    }
