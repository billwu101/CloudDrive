from __future__ import annotations

from typing import Any

import httpx

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMInvalidResponseError,
    LLMMessage,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
    LLMUnavailableError,
)


class ExternalLLMClient:
    """OpenAI-compatible chat completions client used only after privacy routing."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        timeout: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
        }
        if response_format is not None:
            payload["response_format"] = response_format
        if tools:
            payload["tools"] = [_to_openai_tool(t) for t in tools]

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/chat/completions", json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _is_credential_error(exc.response):
                raise ExternalAuthError("External credential was rejected") from exc
            raise LLMUnavailableError("External assistant model is unavailable") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError("External assistant model is unavailable") from exc

        return _parse_openai_response(response.json(), self._model)


def _is_credential_error(response: httpx.Response) -> bool:
    """True when the provider rejected the credential itself: an invalid key
    (401/403) or an exhausted quota (429 with type/code mentioning quota/billing).
    A plain 429 rate-limit is transient and not treated as a credential error."""
    status = response.status_code
    if status in (401, 403):
        return True
    if status == 429:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            return False
        marker = f"{error.get('type', '')} {error.get('code', '')}".lower()
        return "quota" in marker or "billing" in marker or "insufficient" in marker
    return False


def _to_openai_tool(tool: LLMToolDefinition) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def _parse_openai_response(data: object, model: str) -> LLMResponse:
    if not isinstance(data, dict):
        raise LLMInvalidResponseError("External LLM response must be a JSON object")
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise LLMInvalidResponseError("External LLM response is missing choices")
    first = choices[0]
    if not isinstance(first, dict):
        raise LLMInvalidResponseError("External LLM choice must be an object")
    message = first.get("message")
    if not isinstance(message, dict):
        raise LLMInvalidResponseError("External LLM response is missing message")

    content = message.get("content") or ""
    if not isinstance(content, str):
        raise LLMInvalidResponseError("External LLM response content must be a string")

    calls: list[LLMToolCall] = []
    raw_calls = message.get("tool_calls") or []
    if not isinstance(raw_calls, list):
        raise LLMInvalidResponseError("External LLM tool_calls must be a list")
    for raw_call in raw_calls:
        if not isinstance(raw_call, dict):
            continue
        function = raw_call.get("function")
        if not isinstance(function, dict):
            continue
        name = function.get("name")
        arguments = function.get("arguments", {})
        if isinstance(arguments, str):
            arguments = {}
        if isinstance(name, str) and isinstance(arguments, dict):
            calls.append(LLMToolCall(name=name, arguments=arguments))

    return LLMResponse(content=content, tool_calls=calls, model=model)
