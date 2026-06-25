from __future__ import annotations

import json

import httpx

from app.assistant.llm.client import LLMMessage
from app.assistant.llm.ollama import OllamaLLMClient


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
