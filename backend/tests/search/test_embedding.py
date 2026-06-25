from __future__ import annotations

import json

import httpx
import pytest

from app.search.embedding import EmbeddingError, OllamaEmbeddingClient


def _client(handler: httpx.MockTransport) -> OllamaEmbeddingClient:
    return OllamaEmbeddingClient(
        base_url="http://ollama:11434", model="nomic-embed-text", transport=handler
    )


async def test_embed_parses_vector() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": [0.1, 0.2, 0.3]})

    vec = await _client(httpx.MockTransport(handler)).embed("hello")
    assert vec == [0.1, 0.2, 0.3]


async def test_embed_posts_model_and_prompt_to_endpoint() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"embedding": [1.0]})

    await _client(httpx.MockTransport(handler)).embed("revenue report")
    assert seen["path"] == "/api/embeddings"
    assert seen["body"] == {"model": "nomic-embed-text", "prompt": "revenue report"}


async def test_embed_http_error_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with pytest.raises(EmbeddingError):
        await _client(httpx.MockTransport(handler)).embed("x")


async def test_embed_missing_field_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"not_embedding": 1})

    with pytest.raises(EmbeddingError):
        await _client(httpx.MockTransport(handler)).embed("x")


async def test_embed_non_numeric_vector_raises() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embedding": ["a", "b"]})

    with pytest.raises(EmbeddingError):
        await _client(httpx.MockTransport(handler)).embed("x")
