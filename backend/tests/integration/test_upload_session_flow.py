"""
Integration tests for chunked resumable upload (proposal §27).

These exercise the real repository, real Postgres and real local storage —
the unit tests use in-memory fakes, so this is where the SQL upsert, the
unique (session_id, chunk_index) constraint and the on-disk merge are proven.
"""

from __future__ import annotations

import hashlib
from typing import Any

import pytest
from httpx import AsyncClient

from app.core.config import get_settings
from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

# Sessions are sliced with the configured chunk size; these tests only need a
# file big enough to span several chunks, so they read it off the response.


async def _start(client: AsyncClient, h: dict[str, str], *, name: str, size: int) -> dict[str, Any]:
    resp = await client.post(
        "/api/v1/upload/sessions",
        headers=h,
        json={"filename": name, "total_size": size},
    )
    assert resp.status_code == 201, resp.text
    body: dict[str, Any] = resp.json()
    return body


def _slice(content: bytes, index: int, chunk_size: int) -> bytes:
    return content[index * chunk_size : (index + 1) * chunk_size]


async def test_full_chunked_upload_produces_the_original_file(client: AsyncClient) -> None:
    token = await register_and_login(client, email="cu1@test.com")
    h = auth_headers(token)
    content = bytes(range(256)) * 200  # ~51 KB of non-repeating bytes

    session = await _start(client, h, name="movie.bin", size=len(content))
    chunk_size = session["chunk_size"]

    for index in range(session["total_chunks"]):
        resp = await client.put(
            f"/api/v1/upload/sessions/{session['id']}/chunks/{index}",
            headers=h,
            content=_slice(content, index, chunk_size),
        )
        assert resp.status_code == 204

    done = await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)
    assert done.status_code == 201, done.text
    item = done.json()
    assert item["name"] == "movie.bin"
    assert item["size_bytes"] == len(content)

    # The file must download back byte-identical.
    got = await client.get(f"/api/v1/download/{item['id']}", headers=h)
    assert got.status_code == 200
    assert got.content == content
    assert hashlib.sha256(got.content).hexdigest() == hashlib.sha256(content).hexdigest()


async def test_resume_sends_only_the_missing_chunk(client: AsyncClient) -> None:
    token = await register_and_login(client, email="cu2@test.com")
    h = auth_headers(token)
    # Sized off the real chunk size so the file genuinely spans three chunks —
    # resuming is only meaningful across a chunk boundary.
    configured = get_settings().upload_chunk_size_bytes
    content = b"r" * (configured * 2 + 512)

    session = await _start(client, h, name="resume.bin", size=len(content))
    chunk_size = session["chunk_size"]
    total = session["total_chunks"]
    assert total == 3

    # Send everything except the first chunk, as if the browser died mid-upload.
    for index in range(1, total):
        await client.put(
            f"/api/v1/upload/sessions/{session['id']}/chunks/{index}",
            headers=h,
            content=_slice(content, index, chunk_size),
        )

    # Completing now must fail without destroying the session.
    early = await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)
    assert early.status_code == 400
    assert early.json()["error"]["code"] == "INVALID_OPERATION"

    # Resuming tells the client exactly which chunk is missing.
    status = await client.get(f"/api/v1/upload/sessions/{session['id']}", headers=h)
    assert status.status_code == 200
    assert status.json()["uploaded_chunks"] == list(range(1, total))
    assert status.json()["status"] == "uploading"

    await client.put(
        f"/api/v1/upload/sessions/{session['id']}/chunks/0",
        headers=h,
        content=_slice(content, 0, chunk_size),
    )
    done = await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)
    assert done.status_code == 201
    assert done.json()["size_bytes"] == len(content)


async def test_resending_a_chunk_is_idempotent(client: AsyncClient) -> None:
    """The unique (session_id, chunk_index) index must upsert, not duplicate."""
    token = await register_and_login(client, email="cu3@test.com")
    h = auth_headers(token)
    content = b"z" * 5000

    session = await _start(client, h, name="idem.bin", size=len(content))
    chunk_size = session["chunk_size"]

    for _ in range(3):
        resp = await client.put(
            f"/api/v1/upload/sessions/{session['id']}/chunks/0",
            headers=h,
            content=_slice(content, 0, chunk_size),
        )
        assert resp.status_code == 204

    status = await client.get(f"/api/v1/upload/sessions/{session['id']}", headers=h)
    assert status.json()["uploaded_chunks"] == [0]  # one row, not three

    done = await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)
    assert done.status_code == 201
    assert done.json()["size_bytes"] == len(content)


async def test_completed_upload_charges_the_quota_once(client: AsyncClient) -> None:
    token = await register_and_login(client, email="cu4@test.com")
    h = auth_headers(token)
    content = b"q" * 3000

    before = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]

    session = await _start(client, h, name="quota.bin", size=len(content))
    await client.put(
        f"/api/v1/upload/sessions/{session['id']}/chunks/0", headers=h, content=content
    )
    await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)

    after = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]
    assert after - before == len(content)


async def test_cancel_frees_nothing_and_blocks_further_chunks(client: AsyncClient) -> None:
    token = await register_and_login(client, email="cu5@test.com")
    h = auth_headers(token)
    content = b"c" * 2000

    before = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]
    session = await _start(client, h, name="cancel.bin", size=len(content))
    await client.put(
        f"/api/v1/upload/sessions/{session['id']}/chunks/0", headers=h, content=content
    )

    cancelled = await client.delete(f"/api/v1/upload/sessions/{session['id']}", headers=h)
    assert cancelled.status_code == 204

    # A cancelled session is terminal and never touched the quota.
    late = await client.put(
        f"/api/v1/upload/sessions/{session['id']}/chunks/0", headers=h, content=content
    )
    assert late.status_code == 400
    after = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]
    assert after == before


async def test_another_user_cannot_see_or_touch_the_session(client: AsyncClient) -> None:
    owner = auth_headers(await register_and_login(client, email="cu6a@test.com"))
    stranger = auth_headers(await register_and_login(client, email="cu6b@test.com"))

    session = await _start(client, owner, name="private.bin", size=100)

    # Existence must not leak: every entry point answers 404, not 403.
    assert (
        await client.get(f"/api/v1/upload/sessions/{session['id']}", headers=stranger)
    ).status_code == 404
    assert (
        await client.put(
            f"/api/v1/upload/sessions/{session['id']}/chunks/0",
            headers=stranger,
            content=b"x",
        )
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=stranger)
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/upload/sessions/{session['id']}", headers=stranger)
    ).status_code == 404


async def test_same_name_upload_is_auto_renamed(client: AsyncClient) -> None:
    token = await register_and_login(client, email="cu7@test.com")
    h = auth_headers(token)
    content = b"n" * 100

    for _ in range(2):
        session = await _start(client, h, name="dup.txt", size=len(content))
        await client.put(
            f"/api/v1/upload/sessions/{session['id']}/chunks/0", headers=h, content=content
        )
        last = await client.post(f"/api/v1/upload/sessions/{session['id']}/complete", headers=h)
        assert last.status_code == 201

    assert last.json()["name"] == "dup (1).txt"
