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


def _capturing_client(captured: dict[str, object], **kwargs: object) -> OllamaLLMClient:
    async def handler(request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"message": {"content": "{}"}})

    return OllamaLLMClient(
        base_url="http://ollama.test",
        model="gemma4:26b",
        transport=httpx.MockTransport(handler),
        **kwargs,  # type: ignore[arg-type]
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
    # Default construction keeps the original pinned-0 sampling behaviour.
    assert payload["options"]["temperature"] == 0


async def test_ollama_client_uses_configured_structured_temperature() -> None:
    # DEC-031: structured requests use the configured temperature (low, non-zero)
    # instead of a hard-pinned 0 — the grammar guarantees the format at any
    # temperature, while non-zero sampling breaks greedy repetition loops.
    captured: dict[str, object] = {}
    client = _capturing_client(captured, structured_temperature=0.2)

    await client.chat(
        [LLMMessage(role="user", content="plan it")],
        [],
        num_ctx=4096,
        response_format=_ENVELOPE_FORMAT,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["options"]["temperature"] == 0.2


async def test_ollama_client_per_call_temperature_overrides_structured_pin() -> None:
    # A caller (codegen) may need full sampling despite sending a format grammar
    # — the per-call temperature must win over the structured pin.
    captured: dict[str, object] = {}
    client = _capturing_client(captured, structured_temperature=0.2)

    await client.chat(
        [LLMMessage(role="user", content="write a skill")],
        [],
        num_ctx=4096,
        response_format=_ENVELOPE_FORMAT,
        temperature=0.8,
    )

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["options"]["temperature"] == 0.8


async def test_ollama_client_caps_generation_with_num_predict() -> None:
    # DEC-031: num_predict bounds every local request so a repetition loop fails
    # bounded instead of eating the full read timeout — plain chat included.
    captured: dict[str, object] = {}
    client = _capturing_client(captured, num_predict=4096)

    await client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=4096)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["options"]["num_predict"] == 4096


async def test_ollama_client_disable_thinking_flag() -> None:
    # E8 experiment knob: when enabled every request carries think=false;
    # default construction must not send the field at all.
    captured: dict[str, object] = {}
    client = _capturing_client(captured, disable_thinking=True)
    await client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=4096)
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["think"] is False

    captured2: dict[str, object] = {}
    default_client = _capturing_client(captured2)
    await default_client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=4096)
    payload2 = captured2["payload"]
    assert isinstance(payload2, dict)
    assert "think" not in payload2


async def test_ollama_client_omits_num_predict_when_uncapped() -> None:
    # num_predict=0 (and the default) must leave generation uncapped for
    # backward compatibility — e.g. external named Ollama connections.
    captured: dict[str, object] = {}
    client = _capturing_client(captured, num_predict=0)

    await client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=4096)

    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert "num_predict" not in payload["options"]


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
