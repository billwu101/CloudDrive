from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from app.assistant.llm.client import ExternalAuthError, LLMMessage, LLMUnavailableError
from app.assistant.llm.external import ExternalLLMClient


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> ExternalLLMClient:
    return ExternalLLMClient(
        base_url="http://x/v1",
        model="gpt-5.5",
        api_key="sk-test",
        transport=httpx.MockTransport(handler),
    )


async def _chat(client: ExternalLLMClient) -> str:
    resp = await client.chat([LLMMessage(role="user", content="hi")], [], num_ctx=1000)
    return resp.content


async def test_success() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    assert await _chat(_client(handler)) == "hello"


async def test_401_is_auth_error() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "invalid key"}})

    with pytest.raises(ExternalAuthError):
        await _chat(_client(handler))


async def test_403_is_auth_error() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "forbidden"}})

    with pytest.raises(ExternalAuthError):
        await _chat(_client(handler))


async def test_429_insufficient_quota_is_auth_error() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"type": "insufficient_quota"}})

    with pytest.raises(ExternalAuthError):
        await _chat(_client(handler))


async def test_429_rate_limit_is_transient_unavailable() -> None:
    # A plain rate-limit is not a credential problem.
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"type": "rate_limit_exceeded"}})

    with pytest.raises(LLMUnavailableError):
        await _chat(_client(handler))


async def test_500_is_unavailable() -> None:
    def handler(_r: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(LLMUnavailableError):
        await _chat(_client(handler))
