from __future__ import annotations

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
    def __init__(self, *, base_url: str, model: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

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
        if tools:
            payload["tools"] = [_to_ollama_tool(t) for t in tools]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(f"{self._base_url}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMUnavailableError("Local assistant model is unavailable") from exc

        return _parse_ollama_response(response.json(), self._model)


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
