"""Upload validation, quota and storage layout — API-UP-04~15.

Where the other upload suite covers the happy chunked path, this one covers the
refusals and the things that are only true on disk: that a rejected upload
leaves nothing behind, and that the bytes are filed under an opaque key rather
than under whatever the client called the file (proposal §17.3 items 5 and 7).
"""

from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from tests.integration.conftest import (
    _STORAGE_DIR,
    _SessionFactory,
    auth_headers,
    register_and_login,
)

pytestmark = pytest.mark.asyncio


def _stored_files() -> set[Path]:
    """Every blob currently on disk, excluding in-flight chunk uploads."""
    root = Path(_STORAGE_DIR)
    return {
        p for p in root.rglob("*") if p.is_file() and "uploads" not in p.relative_to(root).parts
    }


async def _shrink_quota(email: str, *, quota_bytes: int) -> None:
    async with _SessionFactory() as session:
        await session.execute(
            text("UPDATE users SET quota_bytes = :q WHERE email = :e"),
            {"q": quota_bytes, "e": email},
        )
        await session.commit()


async def _quota(client: AsyncClient, headers: dict[str, str]) -> dict[str, int]:
    resp = await client.get("/api/v1/users/me/quota", headers=headers)
    assert resp.status_code == 200, resp.text
    return dict(resp.json())


async def test_uploading_charges_the_quota_by_exactly_the_file_size(
    client: AsyncClient,
) -> None:
    """API-UP-04 — an off-by-a-chunk here silently strands storage."""
    h = auth_headers(await register_and_login(client, email="quota-add@test.com"))
    before = await _quota(client, h)

    payload = b"z" * 4096
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("blob.bin", io.BytesIO(payload), "application/octet-stream")},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["size_bytes"] == len(payload)

    after = await _quota(client, h)
    assert after["used_bytes"] == before["used_bytes"] + len(payload)
    assert after["available_bytes"] == before["available_bytes"] - len(payload)


async def test_a_clashing_filename_is_auto_numbered_into_a_separate_item(
    client: AsyncClient,
) -> None:
    """API-UP-05 — uploading twice must not overwrite the first file."""
    h = auth_headers(await register_and_login(client, email="clash@test.com"))

    first = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("notes.txt", io.BytesIO(b"first"), "text/plain")},
    )
    second = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("notes.txt", io.BytesIO(b"second"), "text/plain")},
    )
    assert first.status_code == 201 and second.status_code == 201
    assert second.json()["name"] == "notes (1).txt"
    assert first.json()["id"] != second.json()["id"]

    # Both are still independently retrievable with their own content.
    a = await client.get(f"/api/v1/download/{first.json()['id']}", headers=h)
    b = await client.get(f"/api/v1/download/{second.json()['id']}", headers=h)
    assert a.content == b"first"
    assert b.content == b"second"


async def test_a_quota_refusal_writes_nothing_to_disk(client: AsyncClient) -> None:
    """API-UP-06 and API-UP-08.

    The quota check runs before the stream is opened, so a refusal must leave
    the blob store byte-for-byte as it was. Asserts the status code the code
    actually returns — **413**, from `QuotaExceededError`; proposal §19 lists
    容量不足 under 409, which is a documentation mismatch rather than a bug in
    this path.
    """
    email = "quota-full@test.com"
    h = auth_headers(await register_and_login(client, email=email))
    await _shrink_quota(email, quota_bytes=16)

    before = _stored_files()
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("too-big.bin", io.BytesIO(b"y" * 1024), "application/octet-stream")},
    )

    assert resp.status_code == 413, resp.text
    assert resp.json()["error"]["code"] == "QUOTA_EXCEEDED"
    assert _stored_files() == before, "a refused upload left a blob behind"

    listing = await client.get("/api/v1/drive/items", headers=h)
    assert "too-big.bin" not in [i["name"] for i in listing.json()["items"]]


async def test_the_stored_key_never_contains_the_original_filename(
    client: AsyncClient,
) -> None:
    """API-UP-12 — proposal §17.3 item 5.

    Checked on the filesystem rather than through the API, because the API
    deliberately never exposes `storage_key`. Using the original name as the key
    would make the store guessable and would break the moment a file is renamed.
    """
    h = auth_headers(await register_and_login(client, email="opaque@test.com"))
    distinctive = f"payroll-{uuid4().hex}"

    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": (f"{distinctive}.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert resp.status_code == 201, resp.text

    root = Path(_STORAGE_DIR)
    offenders = [str(p.relative_to(root)) for p in _stored_files() if distinctive in str(p)]
    assert not offenders, f"the filename leaked into the storage key: {offenders}"


@pytest.mark.parametrize(
    "filename",
    [
        "../../escape.txt",
        "nested/child.txt",
        "back\\slash.txt",
        "",
        "x" * 513,
    ],
)
async def test_dangerous_filenames_are_refused(client: AsyncClient, filename: str) -> None:
    """API-UP-10 and API-UP-11 — proposal §17.3 item 7.

    The storage layer has its own traversal guard, but a name containing a
    separator must never get that far: it would also corrupt the drive listing
    and the download filename header.
    """
    h = auth_headers(await register_and_login(client, email=f"danger{len(filename)}@test.com"))

    before = _stored_files()
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": (filename, io.BytesIO(b"payload"), "text/plain")},
    )

    assert resp.status_code >= 400, f"{filename!r} was accepted: {resp.text}"
    assert _stored_files() == before, f"{filename!r} was refused but still wrote a blob"


async def test_uploading_into_another_users_folder_is_refused(client: AsyncClient) -> None:
    """API-UP-13 — proposal §14.3 item 1."""
    owner = auth_headers(await register_and_login(client, email="folder-owner@test.com"))
    folder = await client.post("/api/v1/drive/folders", json={"name": "Mine"}, headers=owner)
    folder_id = folder.json()["id"]

    intruder = auth_headers(
        await register_and_login(client, email="folder-intruder@test.com", username="fi")
    )

    resp = await client.post(
        f"/api/v1/upload/simple?parent_id={folder_id}",
        headers=intruder,
        files={"file": ("dropped.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert resp.status_code in (403, 404), resp.text

    listing = await client.get(f"/api/v1/drive/items?parent_id={folder_id}", headers=owner)
    assert listing.json()["items"] == []


async def test_uploading_into_a_missing_parent_is_refused(client: AsyncClient) -> None:
    """API-UP-14."""
    h = auth_headers(await register_and_login(client, email="no-parent@test.com"))

    resp = await client.post(
        f"/api/v1/upload/simple?parent_id={uuid4()}",
        headers=h,
        files={"file": ("orphan.txt", io.BytesIO(b"x"), "text/plain")},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] == "NOT_FOUND"


async def test_uploading_into_a_file_is_refused(client: AsyncClient) -> None:
    """API-UP-15 — a file is not a folder, even though both are drive_items."""
    h = auth_headers(await register_and_login(client, email="parent-is-file@test.com"))

    parent = await client.post(
        "/api/v1/upload/simple",
        headers=h,
        files={"file": ("host.txt", io.BytesIO(b"x"), "text/plain")},
    )
    parent_id = parent.json()["id"]

    resp = await client.post(
        f"/api/v1/upload/simple?parent_id={parent_id}",
        headers=h,
        files={"file": ("guest.txt", io.BytesIO(b"y"), "text/plain")},
    )
    assert resp.status_code >= 400, resp.text
    assert resp.json()["error"]["code"] == "INVALID_OPERATION"
