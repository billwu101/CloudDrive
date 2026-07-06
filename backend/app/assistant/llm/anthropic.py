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


class AnthropicLLMClient:
    """Anthropic Messages API client for Claude model connections."""

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
        system_parts: list[str] = []
        request_messages: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
            elif message.role in {"user", "assistant"}:
                request_messages.append({"role": message.role, "content": message.content})

        if response_format is not None:
            system_parts.append("Respond with valid JSON only.")

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": min(num_ctx, 4096),
            "messages": request_messages,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if tools:
            payload["tools"] = [_to_anthropic_tool(t) for t in tools]

        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, headers=headers, transport=self._transport
            ) as client:
                response = await client.post(f"{self._base_url}/v1/messages", json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if _is_credential_error(exc.response):
                raise ExternalAuthError("Anthropic credential was rejected") from exc
            raise LLMUnavailableError("Anthropic assistant model is unavailable") from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError("Anthropic assistant model is unavailable") from exc

        return _parse_anthropic_response(response.json(), self._model)


def _is_credential_error(response: httpx.Response) -> bool:
    if response.status_code in (401, 403):
        return True
    if response.status_code == 429:
        try:
            text = str(response.json()).lower()
        except ValueError:
            return False
        return "quota" in text or "billing" in text or "credit" in text
    return False


def _to_anthropic_tool(tool: LLMToolDefinition) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.parameters,
    }


def _parse_anthropic_response(data: object, model: str) -> LLMResponse:
    if not isinstance(data, dict):
        raise LLMInvalidResponseError("Anthropic response must be a JSON object")
    content = data.get("content")
    if not isinstance(content, list):
        raise LLMInvalidResponseError("Anthropic response is missing content")

    text_parts: list[str] = []
    calls: list[LLMToolCall] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text" and isinstance(block.get("text"), str):
            text_parts.append(block["text"])
        if block_type == "tool_use":
            name = block.get("name")
            arguments = block.get("input", {})
            if isinstance(name, str) and isinstance(arguments, dict):
                calls.append(LLMToolCall(name=name, arguments=arguments))

    return LLMResponse(content="\n".join(text_parts), tool_calls=calls, model=model)
