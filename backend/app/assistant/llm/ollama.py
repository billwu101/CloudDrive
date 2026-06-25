from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import httpx

from app.assistant.llm.client import (
    LLMInvalidResponseError,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
    LLMUnavailableError,
)


class OllamaLLMClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        api_key: str = "",
        keep_alive: str = "",
        fallback_base_urls: list[str] | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        connect_timeout: float = 5.0,
    ) -> None:
        # Primary first, then any fallbacks; chat() tries them in order and only
        # raises once every endpoint has failed.
        self._base_urls = [base_url.rstrip("/")] + [
            u.rstrip("/") for u in (fallback_base_urls or []) if u
        ]
        self._model = model
        self._timeout = timeout
        self._api_key = api_key
        self._keep_alive = keep_alive
        self._transport = transport
        # Connecting must fail fast (a down/unreachable Ollama shouldn't hang for
        # the full generation timeout); reading keeps the long timeout for slow
        # token generation.
        self._connect_timeout = min(connect_timeout, timeout)

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"num_ctx": num_ctx},
        }
        if self._keep_alive:
            payload["keep_alive"] = self._keep_alive
        if tools:
            payload["tools"] = [_to_ollama_tool(t) for t in tools]
        headers = _auth_headers(self._api_key)

        last_exc: httpx.HTTPError | None = None
        for base_url in self._base_urls:
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self._timeout, connect=self._connect_timeout),
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        f"{base_url}/api/chat",
                        json=payload,
                        headers=headers,
                    )
                    response.raise_for_status()
                return _parse_ollama_response(response.json(), self._model)
            except httpx.HTTPError as exc:
                last_exc = exc
                continue

        raise LLMUnavailableError("Local assistant model is unavailable") from last_exc


def _auth_headers(api_key: str) -> Mapping[str, str] | None:
    if not api_key:
        return None
    return {"Authorization": f"Bearer {api_key}"}


def _to_ollama_tool(tool: LLMToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_ollama_response(data: object, model: str) -> LLMResponse:
    if not isinstance(data, dict):
        raise LLMInvalidResponseError("LLM response must be a JSON object")
    message = data.get("message")
    if not isinstance(message, dict):
        raise LLMInvalidResponseError("LLM response is missing message")

    content = message.get("content", "")
    if not isinstance(content, str):
        raise LLMInvalidResponseError("LLM response content must be a string")

    calls: list[LLMToolCall] = []
    raw_calls = message.get("tool_calls", [])
    if raw_calls is None:
        raw_calls = []
    if not isinstance(raw_calls, list):
        raise LLMInvalidResponseError("LLM tool_calls must be a list")
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            continue
        function = raw_call.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        arguments = function.get("arguments", {})
        if isinstance(name, str) and isinstance(arguments, dict):
            calls.append(LLMToolCall(name=name, arguments=arguments))

    return LLMResponse(content=content, tool_calls=calls, model=model)
