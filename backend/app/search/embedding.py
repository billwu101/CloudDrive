from __future__ import annotations

from abc import ABC, abstractmethod

import httpx


class EmbeddingError(Exception):
    """Raised when an embedding can't be produced (service down / bad response)."""


class EmbeddingClient(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Return the embedding vector for ``text``."""


class OllamaEmbeddingClient(EmbeddingClient):
    """Embeddings via Ollama's /api/embeddings endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout: float = 30.0,
        api_key: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._api_key = api_key
        self._transport = transport

    async def embed(self, text: str) -> list[float]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else None
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self._base_url}/api/embeddings",
                    json={"model": self._model, "prompt": text},
                    headers=headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise EmbeddingError("Embedding service is unavailable") from exc

        data = response.json()
        vector = data.get("embedding") if isinstance(data, dict) else None
        if not isinstance(vector, list) or not vector:
            raise EmbeddingError("Embedding response is missing 'embedding'")
        try:
            return [float(x) for x in vector]
        except (TypeError, ValueError) as exc:
            raise EmbeddingError("Embedding vector is not numeric") from exc
