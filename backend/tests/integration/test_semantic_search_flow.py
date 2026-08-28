"""Integration tests for semantic search and embedding backfill.

Covers ``GET /search/semantic`` and ``POST /search/embeddings/backfill``
(doc/test-cases.md API-SEARCH-04 / API-SEARCH-05 / API-SEARCH-06, proposal
section 5.1-11 and section 24-1).

Two things are deliberately real here: Postgres (pgvector distance ordering,
the DISTINCT ON "best chunk per file" query, the FK cascade) and the whole HTTP
stack. The only stubbed piece is the *network call to the embedding model*,
which no CI box has. The stub is installed by replacing
``app.search.factory.build_embedding_client``; it still honours
``Settings.embedding_enabled``, so the on/off branch under test stays the
production one. Tests that need a genuine model are marked ``needs_llm`` and
skip themselves when the configured endpoint does not answer.
"""

from __future__ import annotations

import io
import math
import os
import re
import socket
from collections.abc import Iterator, Sequence
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select

from app.core.config import Settings, get_settings
from app.models.file_embedding import EMBEDDING_DIM, FileEmbedding
from app.search import factory as search_factory
from app.search.embedding import EmbeddingClient, EmbeddingError, OllamaEmbeddingClient
from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

_SEMANTIC_URL = "/api/v1/search/semantic"
_BACKFILL_URL = "/api/v1/search/embeddings/backfill"

# Documents used across the tests. Only the words listed in _VOCAB below carry
# any weight in the stub embedding, so the expected ranking is exact rather
# than "probably".
_WILDLIFE = "Zebra herds cross the savanna every dry season."
_BIRDS = "Penguin colonies huddle on the antarctic ice all winter."
_FINANCE = "Quarterly revenue climbed after the spring campaign."

_VOCAB: tuple[str, ...] = (
    "zebra",
    "savanna",
    "penguin",
    "antarctic",
    "quarterly",
    "revenue",
)
_VOCAB_INDEX = {word: position for position, word in enumerate(_VOCAB)}
# Bucket for text containing none of the vocabulary. A file must never embed to
# the all-zero vector: pgvector's cosine_distance against a zero vector is NaN,
# which would make result ordering undefined.
_OTHER_BUCKET = len(_VOCAB)


class _StubEmbeddingClient(EmbeddingClient):
    """Deterministic stand-in for the Ollama embedding endpoint.

    Each word of ``_VOCAB`` owns one dimension; everything else is ignored. The
    result is L2-normalised, so cosine similarity between a one-word query and
    a document is exactly ``matches / sqrt(document_terms)`` and the expected
    ranking can be asserted numerically. ``calls`` records every text that
    reached the model, so a test can prove a short-circuit really short-circuited.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        vector = [0.0] * EMBEDDING_DIM
        for word in re.findall(r"[a-z]+", text.lower()):
            position = _VOCAB_INDEX.get(word)
            if position is not None:
                vector[position] += 1.0
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0.0:
            vector[_OTHER_BUCKET] = 1.0
            return vector
        return [value / norm for value in vector]


class _EmbeddingEnv:
    """Moves the running app between "semantic search off" and "on" mid-test.

    ``get_settings`` is ``@lru_cache``d but the search router calls it on every
    request, so setting the environment variable and clearing the cache is
    enough. Starts disabled so a developer .env cannot change what a test means.
    """

    _KEYS = ("EMBEDDING_ENABLED", "EMBEDDING_BASE_URL", "LLM_TIMEOUT_SECONDS")

    def __init__(self) -> None:
        self._saved: dict[str, str | None] = {key: os.environ.get(key) for key in self._KEYS}
        self.disable()

    def enable(self, *, base_url: str | None = None, timeout_seconds: float = 2.0) -> None:
        os.environ["EMBEDDING_ENABLED"] = "true"
        if base_url is not None:
            os.environ["EMBEDDING_BASE_URL"] = base_url
        os.environ["LLM_TIMEOUT_SECONDS"] = str(timeout_seconds)
        get_settings.cache_clear()

    def disable(self) -> None:
        os.environ["EMBEDDING_ENABLED"] = "false"
        get_settings.cache_clear()

    def restore(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        get_settings.cache_clear()


@pytest.fixture
def embedding_env() -> Iterator[_EmbeddingEnv]:
    """Semantic search forced off, with enable()/disable() for the test to drive."""
    env = _EmbeddingEnv()
    try:
        yield env
    finally:
        env.restore()


@pytest.fixture
def stub_embeddings(monkeypatch: pytest.MonkeyPatch) -> _StubEmbeddingClient:
    """Replace only the embedding HTTP client; the enabled/disabled branch stays real."""
    client = _StubEmbeddingClient()

    def _build(settings: Settings) -> EmbeddingClient | None:
        return client if settings.embedding_enabled else None

    monkeypatch.setattr(search_factory, "build_embedding_client", _build)
    return client


def _closed_local_port() -> int:
    """A loopback port with nothing listening, so connecting fails immediately."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


async def _upload_text(client: AsyncClient, headers: dict[str, str], name: str, body: str) -> UUID:
    """Upload a text file (which the indexer extracts) and return its item id."""
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=headers,
        files={"file": (name, io.BytesIO(body.encode("utf-8")), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return UUID(resp.json()["id"])


async def _count_embeddings(item_ids: Sequence[UUID]) -> int:
    """Number of file_embeddings rows stored for these items, read straight from the DB."""
    if not item_ids:
        return 0
    async with _SessionFactory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(FileEmbedding)
            .where(FileEmbedding.item_id.in_(list(item_ids)))
        )
        return int(result.scalar_one())


async def _stored_chunks(item_id: UUID) -> list[tuple[int, str, str]]:
    """(chunk_index, snippet, model) rows stored for one item, ordered by chunk."""
    async with _SessionFactory() as session:
        result = await session.execute(
            select(FileEmbedding.chunk_index, FileEmbedding.snippet, FileEmbedding.model)
            .where(FileEmbedding.item_id == item_id)
            .order_by(FileEmbedding.chunk_index)
        )
        return [(int(row[0]), str(row[1]), str(row[2])) for row in result.all()]


# --- Semantic search disabled: the state CI and most deployments actually run in ---


async def test_semantic_search_returns_503_when_embeddings_are_disabled(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-05 - the off switch must degrade, not explode.

    Pins the real contract: 503 with a plain FastAPI ``detail`` body. Note this
    contradicts doc/test-cases.md, which describes API-SEARCH-05 as "falls back
    to normal search" - the backend does no such fallback, the caller has to.
    """
    token = await register_and_login(client, email="sem-off@test.com", username="semoff")
    headers = auth_headers(token)
    await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)

    resp = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)

    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "Semantic search is not enabled"}


async def test_keyword_search_still_works_while_semantic_search_is_disabled(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-05 - the degraded path a client falls back to must be intact.

    A 503 from /search/semantic is only acceptable because plain /search still
    answers from the full-text index, so this asserts both in one flow.
    """
    token = await register_and_login(client, email="sem-fallback@test.com", username="semfb")
    headers = auth_headers(token)
    item_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)

    semantic = await client.get(_SEMANTIC_URL, params={"q": "savanna"}, headers=headers)
    assert semantic.status_code == 503, semantic.text

    keyword = await client.get("/api/v1/search", params={"q": "savanna"}, headers=headers)
    assert keyword.status_code == 200, keyword.text
    body = keyword.json()
    assert body["total"] == 1
    assert [UUID(item["id"]) for item in body["items"]] == [item_id]
    assert body["items"][0]["name"] == "wildlife.txt"


async def test_backfill_returns_503_and_writes_nothing_when_disabled(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-05 - backfill refuses the same way, and leaves no partial state (A3)."""
    token = await register_and_login(client, email="bf-off@test.com", username="bfoff")
    headers = auth_headers(token)
    item_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)

    resp = await client.post(_BACKFILL_URL, headers=headers)

    assert resp.status_code == 503, resp.text
    assert resp.json() == {"detail": "Semantic search is not enabled"}
    assert await _count_embeddings([item_id]) == 0


async def test_semantic_endpoints_reject_an_invalid_token(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-06 support - auth is checked before the feature flag.

    A disabled feature must not become an unauthenticated one: both endpoints
    answer 401 in the documented error envelope, not the 503 they would return
    for an authenticated caller.
    """
    bad = {"Authorization": "Bearer not-a-real-token"}

    semantic = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=bad)
    backfill = await client.post(_BACKFILL_URL, headers=bad)

    assert semantic.status_code == 401, semantic.text
    assert backfill.status_code == 401, backfill.text
    assert semantic.json()["error"]["code"] == "UNAUTHORIZED"
    assert backfill.json()["error"]["code"] == "UNAUTHORIZED"


# --- Semantic search enabled (stubbed model, real pgvector) ---


async def test_semantic_search_ranks_the_matching_file_first(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-04 - upload indexes an embedding, and the query ranks by it (A3).

    Also pins two behaviours worth knowing about: every readable file comes
    back (there is no minimum-score cutoff, unrelated files just score 0), and
    the stored snippet is the chunk text used for the result preview.
    """
    embedding_env.enable()
    token = await register_and_login(client, email="sem-on@test.com", username="semon")
    headers = auth_headers(token)
    wildlife_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)
    birds_id = await _upload_text(client, headers, "birds.txt", _BIRDS)
    finance_id = await _upload_text(client, headers, "finance.txt", _FINANCE)

    # A3: the upload path really wrote a vector row per file, tagged with the model.
    assert await _count_embeddings([wildlife_id, birds_id, finance_id]) == 3
    assert await _stored_chunks(wildlife_id) == [(0, _WILDLIFE, get_settings().embedding_model)]

    resp = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)

    assert resp.status_code == 200, resp.text
    hits = resp.json()
    assert len(hits) == 3
    assert UUID(hits[0]["item"]["id"]) == wildlife_id
    assert hits[0]["item"]["name"] == "wildlife.txt"
    assert hits[0]["snippet"] == _WILDLIFE
    # "zebra" is 1 of the 2 vocabulary terms in _WILDLIFE, both unit-weighted.
    assert hits[0]["score"] == pytest.approx(2**-0.5, abs=1e-3)
    assert [hit["score"] for hit in hits[1:]] == pytest.approx([0.0, 0.0], abs=1e-5)


async def test_semantic_search_limit_caps_the_result_count(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-04 - ``limit`` truncates from the top of the ranking, not arbitrarily."""
    embedding_env.enable()
    token = await register_and_login(client, email="sem-limit@test.com", username="semlim")
    headers = auth_headers(token)
    wildlife_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)
    await _upload_text(client, headers, "birds.txt", _BIRDS)
    await _upload_text(client, headers, "finance.txt", _FINANCE)

    resp = await client.get(_SEMANTIC_URL, params={"q": "zebra", "limit": 2}, headers=headers)

    assert resp.status_code == 200, resp.text
    hits = resp.json()
    assert len(hits) == 2
    assert UUID(hits[0]["item"]["id"]) == wildlife_id


async def test_semantic_search_empty_query_short_circuits_before_the_model(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-04 edge - a blank query returns [] without spending an embed call."""
    embedding_env.enable()
    token = await register_and_login(client, email="sem-blank@test.com", username="semblank")
    headers = auth_headers(token)
    assert stub_embeddings.calls == []

    resp = await client.get(_SEMANTIC_URL, params={"q": "   "}, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == []
    assert stub_embeddings.calls == [], "blank query must not reach the embedding model"


async def test_semantic_search_hides_other_users_files(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-06 (A4) - the best match in the database is invisible to a stranger.

    Bob's query is the one that would rank Alice's file first if the owner
    filter were missing; he must get only his own, unrelated file back.
    """
    embedding_env.enable()
    token_a = await register_and_login(client, email="sem-alice@test.com", username="semalice")
    token_b = await register_and_login(client, email="sem-bob@test.com", username="sembob")
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    alice_id = await _upload_text(client, headers_a, "wildlife.txt", _WILDLIFE)
    bob_id = await _upload_text(client, headers_b, "finance.txt", _FINANCE)

    resp_b = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers_b)
    assert resp_b.status_code == 200, resp_b.text
    ids_b = [UUID(hit["item"]["id"]) for hit in resp_b.json()]
    assert alice_id not in ids_b, "semantic search leaked another user's file"
    assert ids_b == [bob_id]

    # The row does exist and Alice can find it - the filter is scoping, not emptiness.
    resp_a = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers_a)
    assert [UUID(hit["item"]["id"]) for hit in resp_a.json()] == [alice_id]


async def test_semantic_search_includes_a_file_shared_with_me(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-06 (A4) - an explicit share widens the scope, and only that far."""
    embedding_env.enable()
    token_a = await register_and_login(client, email="shr-alice@test.com", username="shralice")
    token_b = await register_and_login(client, email="shr-bob@test.com", username="shrbob")
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)

    shared_id = await _upload_text(client, headers_a, "wildlife.txt", _WILDLIFE)
    private_id = await _upload_text(client, headers_a, "birds.txt", _BIRDS)

    before = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers_b)
    assert before.status_code == 200, before.text
    assert before.json() == []

    share = await client.post(
        f"/api/v1/share/items/{shared_id}",
        json={"target_email": "shr-bob@test.com", "permission": "viewer"},
        headers=headers_a,
    )
    assert share.status_code == 201, share.text

    after = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers_b)
    assert after.status_code == 200, after.text
    ids = [UUID(hit["item"]["id"]) for hit in after.json()]
    assert ids == [shared_id]
    assert private_id not in ids, "an unshared sibling came along with the shared file"


async def test_trashed_file_leaves_and_returns_to_semantic_results(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-07 for the semantic index (A3).

    Trashing must hide the file without discarding its vectors, otherwise
    restore would silently return an unsearchable file.
    """
    embedding_env.enable()
    token = await register_and_login(client, email="sem-trash@test.com", username="semtrash")
    headers = auth_headers(token)
    item_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)

    trashed = await client.post(f"/api/v1/trash/items/{item_id}", headers=headers)
    assert trashed.status_code == 200, trashed.text
    assert trashed.json()["is_deleted"] is True

    hidden = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)
    assert hidden.status_code == 200, hidden.text
    assert hidden.json() == []
    assert await _count_embeddings([item_id]) == 1, "trashing must not drop the vectors"

    restored = await client.post(f"/api/v1/trash/items/{item_id}/restore", headers=headers)
    assert restored.status_code == 200, restored.text

    back = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)
    assert [UUID(hit["item"]["id"]) for hit in back.json()] == [item_id]


async def test_permanent_delete_removes_the_files_embeddings(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-07 (A3) - purging a file takes its vectors with it.

    file_embeddings.item_id is ON DELETE CASCADE; this checks the cascade
    actually fires on the hard-delete path rather than leaving orphan vectors
    that a later query could still surface.
    """
    embedding_env.enable()
    token = await register_and_login(client, email="sem-purge@test.com", username="sempurge")
    headers = auth_headers(token)
    item_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)
    assert await _count_embeddings([item_id]) == 1

    await client.post(f"/api/v1/trash/items/{item_id}", headers=headers)
    purged = await client.delete(f"/api/v1/trash/items/{item_id}", headers=headers)
    assert purged.status_code == 204, purged.text

    assert await _count_embeddings([item_id]) == 0
    remaining = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)
    assert remaining.status_code == 200, remaining.text
    assert remaining.json() == []


# --- Backfill ---


async def test_backfill_embeds_files_uploaded_while_semantic_search_was_off(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-04 (A3) - the whole reason the backfill endpoint exists.

    Uploads happen with EMBEDDING_ENABLED=false (so only the full-text index is
    written), then the flag flips and backfill has to catch those files up
    until they are semantically searchable.
    """
    token = await register_and_login(client, email="bf-on@test.com", username="bfon")
    headers = auth_headers(token)
    wildlife_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)
    finance_id = await _upload_text(client, headers, "finance.txt", _FINANCE)
    assert await _count_embeddings([wildlife_id, finance_id]) == 0

    embedding_env.enable()
    resp = await client.post(_BACKFILL_URL, headers=headers)

    assert resp.status_code == 200, resp.text
    assert resp.json() == {"indexed": 2, "remaining": 0}
    assert await _count_embeddings([wildlife_id, finance_id]) == 2
    assert await _stored_chunks(finance_id) == [(0, _FINANCE, get_settings().embedding_model)]

    # A2: the files are now reachable through the query endpoint, not just the table.
    search = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)
    assert search.status_code == 200, search.text
    assert UUID(search.json()[0]["item"]["id"]) == wildlife_id

    # Re-running is a no-op: nothing is pending any more.
    again = await client.post(_BACKFILL_URL, headers=headers)
    assert again.json() == {"indexed": 0, "remaining": 0}
    assert await _count_embeddings([wildlife_id, finance_id]) == 2


async def test_backfill_processes_one_batch_per_call(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-04 (A3) - ``batch_size`` bounds one call and ``remaining`` drives the next."""
    token = await register_and_login(client, email="bf-batch@test.com", username="bfbatch")
    headers = auth_headers(token)
    item_ids = [
        await _upload_text(client, headers, "wildlife.txt", _WILDLIFE),
        await _upload_text(client, headers, "birds.txt", _BIRDS),
        await _upload_text(client, headers, "finance.txt", _FINANCE),
    ]
    embedding_env.enable()

    first = await client.post(_BACKFILL_URL, params={"batch_size": 2}, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json() == {"indexed": 2, "remaining": 1}
    assert await _count_embeddings(item_ids) == 2

    second = await client.post(_BACKFILL_URL, params={"batch_size": 2}, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json() == {"indexed": 1, "remaining": 0}
    assert await _count_embeddings(item_ids) == 3


async def test_backfill_only_embeds_the_callers_own_files(
    client: AsyncClient, embedding_env: _EmbeddingEnv, stub_embeddings: _StubEmbeddingClient
) -> None:
    """API-SEARCH-06 (A4) - backfill is per-user work, not a global sweep.

    Alice draining her queue must not touch Bob's files, and her ``remaining``
    must not count them either.
    """
    token_a = await register_and_login(client, email="bf-alice@test.com", username="bfalice")
    token_b = await register_and_login(client, email="bf-bob@test.com", username="bfbob")
    headers_a = auth_headers(token_a)
    headers_b = auth_headers(token_b)
    alice_ids = [
        await _upload_text(client, headers_a, "wildlife.txt", _WILDLIFE),
        await _upload_text(client, headers_a, "birds.txt", _BIRDS),
    ]
    bob_id = await _upload_text(client, headers_b, "finance.txt", _FINANCE)
    embedding_env.enable()

    resp_a = await client.post(_BACKFILL_URL, headers=headers_a)
    assert resp_a.status_code == 200, resp_a.text
    assert resp_a.json() == {"indexed": 2, "remaining": 0}
    assert await _count_embeddings(alice_ids) == 2
    assert await _count_embeddings([bob_id]) == 0, "backfill crossed a user boundary"

    resp_b = await client.post(_BACKFILL_URL, headers=headers_b)
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json() == {"indexed": 1, "remaining": 0}
    assert await _count_embeddings([bob_id]) == 1


# --- Enabled, but the embedding service is unreachable ---


async def test_semantic_endpoints_return_503_when_the_embedding_service_is_down(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-05 - "enabled" is not the same as "reachable".

    No stub here: the real OllamaEmbeddingClient is pointed at a closed
    loopback port, so a genuine httpx connection error has to travel through
    EmbeddingError and come out as 503 rather than an unhandled 500.
    """
    token = await register_and_login(client, email="sem-down@test.com", username="semdown")
    headers = auth_headers(token)
    item_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)

    embedding_env.enable(base_url=f"http://127.0.0.1:{_closed_local_port()}")

    semantic = await client.get(_SEMANTIC_URL, params={"q": "zebra"}, headers=headers)
    assert semantic.status_code == 503, semantic.text
    assert semantic.json() == {"detail": "Embedding service is unavailable"}

    backfill = await client.post(_BACKFILL_URL, headers=headers)
    assert backfill.status_code == 503, backfill.text
    assert backfill.json() == {"detail": "Embedding service is unavailable"}
    assert await _count_embeddings([item_id]) == 0


async def test_backfill_succeeds_without_the_model_when_nothing_is_pending(
    client: AsyncClient, embedding_env: _EmbeddingEnv
) -> None:
    """API-SEARCH-04 edge - an empty queue never contacts the embedding service.

    Pins that backfill answers 200 with zeroes for a user who has no indexable
    files, even while the endpoint is unreachable, instead of failing on a
    health check it does not need.
    """
    token = await register_and_login(client, email="bf-empty@test.com", username="bfempty")
    headers = auth_headers(token)
    # A folder has no extracted text, so it never becomes a backfill candidate.
    folder = await client.post("/api/v1/drive/folders", json={"name": "Empty"}, headers=headers)
    assert folder.status_code == 201, folder.text

    embedding_env.enable(base_url=f"http://127.0.0.1:{_closed_local_port()}")

    resp = await client.post(_BACKFILL_URL, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"indexed": 0, "remaining": 0}


# --- Real model (skipped unless one is actually configured and answering) ---


@pytest.mark.needs_llm
async def test_semantic_search_against_the_real_embedding_model(client: AsyncClient) -> None:
    """API-SEARCH-04 with no stub at all - meaning-based retrieval end to end.

    Requires EMBEDDING_ENABLED plus a reachable embedding model, which CI does
    not have, so it probes the configured endpoint first and skips otherwise.
    The query shares no words with the target document: only a real model can
    rank the wildlife note above the finance note here.
    """
    settings = get_settings()
    if not settings.embedding_enabled:
        pytest.skip("EMBEDDING_ENABLED is off; there is no embedding model to talk to")
    probe = OllamaEmbeddingClient(
        base_url=settings.embedding_base_url or settings.llm_base_url,
        model=settings.embedding_model,
        timeout=5.0,
        api_key=settings.llm_api_key,
    )
    try:
        await probe.embed("ping")
    except EmbeddingError:
        pytest.skip("configured embedding endpoint is unreachable")

    token = await register_and_login(client, email="sem-real@test.com", username="semreal")
    headers = auth_headers(token)
    wildlife_id = await _upload_text(client, headers, "wildlife.txt", _WILDLIFE)
    await _upload_text(client, headers, "finance.txt", _FINANCE)
    assert await _count_embeddings([wildlife_id]) >= 1

    resp = await client.get(
        _SEMANTIC_URL,
        params={"q": "which animals graze on african grassland"},
        headers=headers,
    )

    assert resp.status_code == 200, resp.text
    hits = resp.json()
    assert hits, "a configured embedding model returned no semantic hits"
    assert UUID(hits[0]["item"]["id"]) == wildlife_id
    assert hits[0]["score"] > hits[-1]["score"]
