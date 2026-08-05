"""Hierarchy operations — API-MV, API-REN, API-DIR, API-LIST, API-DL.

Moves and renames are the operations where "the endpoint returned 200" is
least trustworthy: both sides of a move have to be checked, because a move that
adds without removing looks identical from the destination.
"""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def _folder(
    client: AsyncClient, h: dict[str, str], name: str, parent: str | None = None
) -> str:
    body: dict[str, object] = {"name": name}
    if parent is not None:
        body["parent_id"] = parent
    resp = await client.post("/api/v1/drive/folders", json=body, headers=h)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _names_in(client: AsyncClient, h: dict[str, str], parent: str | None) -> list[str]:
    url = "/api/v1/drive/items"
    if parent is not None:
        url = f"{url}?parent_id={parent}"
    resp = await client.get(url, headers=h)
    assert resp.status_code == 200, resp.text
    return [i["name"] for i in resp.json()["items"]]


async def test_a_move_is_checked_at_both_ends(client: AsyncClient) -> None:
    """API-MV-01 — a move that copies instead of moving passes a destination-only check."""
    h = auth_headers(await register_and_login(client, email="move-both@test.com"))
    source = await _folder(client, h, "Source")
    dest = await _folder(client, h, "Dest")

    upload = await client.post(
        f"/api/v1/upload/simple?parent_id={source}",
        headers=h,
        files={"file": ("wanderer.txt", io.BytesIO(b"x"), "text/plain")},
    )
    item_id = upload.json()["id"]

    moved = await client.patch(
        f"/api/v1/drive/items/{item_id}/parent", json={"parent_id": dest}, headers=h
    )
    assert moved.status_code == 200, moved.text

    assert "wanderer.txt" in await _names_in(client, h, dest)
    assert "wanderer.txt" not in await _names_in(client, h, source)


async def test_a_folder_cannot_be_moved_into_its_own_subtree(client: AsyncClient) -> None:
    """API-MV-02 — §19 lists 不可移到子孫資料夾 explicitly.

    Succeeding here would detach the whole branch from the root: it would still
    exist in the table but no listing would ever reach it.
    """
    h = auth_headers(await register_and_login(client, email="cycle@test.com"))
    parent = await _folder(client, h, "Parent")
    child = await _folder(client, h, "Child", parent)
    grandchild = await _folder(client, h, "Grandchild", child)

    for target in (child, grandchild):
        resp = await client.patch(
            f"/api/v1/drive/items/{parent}/parent", json={"parent_id": target}, headers=h
        )
        assert resp.status_code >= 400, f"parent was moved under {target}: {resp.text}"

    # Into itself, too.
    onto_self = await client.patch(
        f"/api/v1/drive/items/{parent}/parent", json={"parent_id": parent}, headers=h
    )
    assert onto_self.status_code >= 400, onto_self.text

    # The tree is intact: Parent is still at the root.
    assert "Parent" in await _names_in(client, h, None)


async def test_moving_into_a_missing_folder_is_refused(client: AsyncClient) -> None:
    """API-MV-03."""
    h = auth_headers(await register_and_login(client, email="move-nowhere@test.com"))
    folder = await _folder(client, h, "Stayer")

    resp = await client.patch(
        f"/api/v1/drive/items/{folder}/parent", json={"parent_id": str(uuid4())}, headers=h
    )
    assert resp.status_code >= 400, resp.text
    assert "Stayer" in await _names_in(client, h, None)


async def test_renaming_onto_a_sibling_name_is_refused(client: AsyncClient) -> None:
    """API-REN-02 — §19 lists 同層名稱重複 under 409."""
    h = auth_headers(await register_and_login(client, email="rename-clash@test.com"))
    await _folder(client, h, "Alpha")
    beta = await _folder(client, h, "Beta")

    resp = await client.patch(f"/api/v1/drive/items/{beta}/name", json={"name": "Alpha"}, headers=h)
    assert resp.status_code == 409, resp.text
    assert resp.json()["error"]["code"] == "NAME_CONFLICT"

    names = await _names_in(client, h, None)
    assert sorted(names) == ["Alpha", "Beta"]


async def test_the_same_name_is_fine_in_a_different_folder(client: AsyncClient) -> None:
    """API-DIR-03 — uniqueness is per parent, not global."""
    h = auth_headers(await register_and_login(client, email="same-name@test.com"))
    left = await _folder(client, h, "Left")
    right = await _folder(client, h, "Right")

    a = await _folder(client, h, "Notes", left)
    b = await _folder(client, h, "Notes", right)
    assert a != b

    assert "Notes" in await _names_in(client, h, left)
    assert "Notes" in await _names_in(client, h, right)


async def test_ancestors_come_back_root_first(client: AsyncClient) -> None:
    """API-LIST-03 — the breadcrumb is unusable if the order is not guaranteed."""
    h = auth_headers(await register_and_login(client, email="breadcrumb@test.com"))
    lvl1 = await _folder(client, h, "One")
    lvl2 = await _folder(client, h, "Two", lvl1)
    lvl3 = await _folder(client, h, "Three", lvl2)

    resp = await client.get(f"/api/v1/drive/items/{lvl3}/ancestors", headers=h)
    assert resp.status_code == 200, resp.text
    assert [a["name"] for a in resp.json()] == ["One", "Two"]


async def test_paging_neither_repeats_nor_drops_an_item(client: AsyncClient) -> None:
    """API-LIST-01 — an off-by-one in the offset hides a row for good."""
    h = auth_headers(await register_and_login(client, email="paging@test.com"))
    for n in range(25):
        await _folder(client, h, f"item-{n:02d}")

    first = await client.get("/api/v1/drive/items?page=1&page_size=10", headers=h)
    second = await client.get("/api/v1/drive/items?page=2&page_size=10", headers=h)
    third = await client.get("/api/v1/drive/items?page=3&page_size=10", headers=h)

    assert first.json()["total"] == 25
    ids = [i["id"] for i in first.json()["items"]]
    ids += [i["id"] for i in second.json()["items"]]
    ids += [i["id"] for i in third.json()["items"]]

    assert len(ids) == 25
    assert len(set(ids)) == 25, "a page boundary repeated an item"


async def test_listing_never_shows_another_users_items(client: AsyncClient) -> None:
    """API-LIST-02 — §24 acceptance 1."""
    a = auth_headers(await register_and_login(client, email="tenant-a@test.com"))
    b = auth_headers(await register_and_login(client, email="tenant-b@test.com", username="tb"))

    await _folder(client, a, "A-Only")
    await _folder(client, b, "B-Only")

    assert await _names_in(client, a, None) == ["A-Only"]
    assert await _names_in(client, b, None) == ["B-Only"]


async def test_archive_zips_exactly_what_was_asked_for(client: AsyncClient) -> None:
    """API-DL-02 — §5.1 item 4.

    Also guards the boundary: an unselected sibling must not be swept in by a
    query that fetched the whole parent.
    """
    h = auth_headers(await register_and_login(client, email="zipper@test.com"))
    folder = await _folder(client, h, "Bundle")

    wanted = []
    for name, payload in (("one.txt", b"first"), ("two.txt", b"second")):
        resp = await client.post(
            f"/api/v1/upload/simple?parent_id={folder}",
            headers=h,
            files={"file": (name, io.BytesIO(payload), "text/plain")},
        )
        wanted.append(resp.json()["id"])

    await client.post(
        f"/api/v1/upload/simple?parent_id={folder}",
        headers=h,
        files={"file": ("excluded.txt", io.BytesIO(b"nope"), "text/plain")},
    )

    resp = await client.post("/api/v1/download/archive", json={"item_ids": wanted}, headers=h)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/zip")

    with zipfile.ZipFile(io.BytesIO(resp.content)) as archive:
        entries = archive.namelist()
        assert any(e.endswith("one.txt") for e in entries), entries
        assert any(e.endswith("two.txt") for e in entries), entries
        assert not any(e.endswith("excluded.txt") for e in entries), entries
        payloads = {archive.read(e) for e in entries}
        assert b"first" in payloads and b"second" in payloads


async def test_archiving_another_users_item_is_refused(client: AsyncClient) -> None:
    """API-DL-04 — the archive endpoint takes a list, so it needs its own check."""
    owner = auth_headers(await register_and_login(client, email="zip-owner@test.com"))
    upload = await client.post(
        "/api/v1/upload/simple",
        headers=owner,
        files={"file": ("private.txt", io.BytesIO(b"secret"), "text/plain")},
    )
    item_id = upload.json()["id"]

    intruder = auth_headers(
        await register_and_login(client, email="zip-intruder@test.com", username="zi")
    )
    resp = await client.post(
        "/api/v1/download/archive", json={"item_ids": [item_id]}, headers=intruder
    )
    assert resp.status_code in (403, 404), resp.text
    assert b"secret" not in resp.content


async def test_downloading_a_missing_item_is_a_clean_404(client: AsyncClient) -> None:
    """API-DL-04 — §17.4 item 5: no stack trace, no internal path."""
    h = auth_headers(await register_and_login(client, email="dl-missing@test.com"))

    resp = await client.get(f"/api/v1/download/{uuid4()}", headers=h)
    assert resp.status_code == 404, resp.text
    assert resp.json()["error"]["code"] in ("NOT_FOUND", "ITEM_CONTENT_NOT_FOUND")
