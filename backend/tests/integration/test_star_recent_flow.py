"""Starred and Recent listings — doc/test-cases.md API-STAR-01~04, API-RECENT-01.

Both listings are derived, not stored: starred lives in `user_item_preferences`
and recent is replayed from `activity_logs`. A write returning 200 therefore
proves nothing here — every case writes through one endpoint and reads back
through the endpoint the product actually renders from (level A2).
"""

from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def _upload(
    client: AsyncClient, headers: dict[str, str], name: str, parent: str | None = None
) -> str:
    url = "/api/v1/upload/simple"
    if parent is not None:
        url = f"{url}?parent_id={parent}"
    resp = await client.post(
        url, headers=headers, files={"file": (name, io.BytesIO(b"x" * 8), "text/plain")}
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


async def _star(
    client: AsyncClient, headers: dict[str, str], item_id: str, *, on: bool = True
) -> None:
    resp = await client.put(
        f"/api/v1/drive/items/{item_id}/star", json={"is_starred": on}, headers=headers
    )
    assert resp.status_code == 200, resp.text


async def _starred_ids(client: AsyncClient, headers: dict[str, str]) -> list[str]:
    resp = await client.get("/api/v1/drive/starred", headers=headers)
    assert resp.status_code == 200, resp.text
    return [i["id"] for i in resp.json()]


async def test_starring_a_file_inside_a_subfolder_still_lists_it(client: AsyncClient) -> None:
    """API-STAR-02 — regression for db5b2b7.

    Starred was once "list the root folder, then filter client-side", so
    anything starred inside a subfolder was invisible. The star write itself
    was fine and returned 200; only reading back through /drive/starred with
    the item deliberately *not* at the root exposes it.
    """
    h = auth_headers(await register_and_login(client, email="star-sub@test.com"))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Deep"}, headers=h)
    folder_id = folder.json()["id"]
    nested = await client.post(
        "/api/v1/drive/folders", json={"name": "Deeper", "parent_id": folder_id}, headers=h
    )
    file_id = await _upload(client, h, "buried.txt", parent=nested.json()["id"])

    await _star(client, h, file_id)

    assert file_id in await _starred_ids(client, h)


async def test_starred_list_is_not_capped_by_the_listing_page_size(client: AsyncClient) -> None:
    """API-STAR-02 (second half of db5b2b7) — items past page 1 were also lost.

    The default page size for /drive/items is 20, so 25 starred items is enough
    to catch a starred list that is really a filtered first page.
    """
    h = auth_headers(await register_and_login(client, email="star-page@test.com"))

    ids = []
    for n in range(25):
        item = await client.post(
            "/api/v1/drive/folders", json={"name": f"folder-{n:02d}"}, headers=h
        )
        ids.append(item.json()["id"])
        await _star(client, h, ids[-1])

    starred = await _starred_ids(client, h)
    assert len(starred) == 25
    assert set(starred) == set(ids)


async def test_unstarring_drops_it_from_the_list(client: AsyncClient) -> None:
    """API-STAR-03."""
    h = auth_headers(await register_and_login(client, email="unstar@test.com"))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Temp"}, headers=h)
    item_id = folder.json()["id"]

    await _star(client, h, item_id)
    assert item_id in await _starred_ids(client, h)

    await _star(client, h, item_id, on=False)
    assert item_id not in await _starred_ids(client, h)


async def test_star_is_per_user_not_a_property_of_the_item(client: AsyncClient) -> None:
    """API-STAR-04 — the recipient's star must not leak onto the owner's list.

    `drive_items.is_starred` is a legacy column and is not authoritative; the
    real state is a row in `user_item_preferences`. If the two were ever
    confused, the recipient starring a shared item would light it up for the
    owner too.

    Also pins a **known limitation**: `DriveService.get_starred` filters on
    `item.owner_id == user_id`, so a shared item the recipient stars appears on
    nobody's Starred page — the star is recorded but never listed. That is
    current deliberate behaviour, not something this test is asking to change;
    it is asserted here so that changing it is a conscious decision rather than
    a silent drift.
    """
    owner = auth_headers(await register_and_login(client, email="star-owner@test.com"))
    guest_email = "star-guest@test.com"
    guest = auth_headers(await register_and_login(client, email=guest_email, username="starguest"))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Shared"}, headers=owner)
    item_id = folder.json()["id"]
    share = await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": guest_email, "permission": "viewer"},
        headers=owner,
    )
    assert share.status_code in (200, 201), share.text

    await _star(client, guest, item_id)

    # The guarantee that matters: one user's star never reaches another's list.
    assert item_id not in await _starred_ids(client, owner)
    # The known limitation, pinned deliberately (see docstring).
    assert item_id not in await _starred_ids(client, guest)

    # And the owner's own star still works and stays their own.
    await _star(client, owner, item_id)
    assert item_id in await _starred_ids(client, owner)
    assert item_id not in await _starred_ids(client, guest)


async def test_trashed_items_leave_the_starred_list(client: AsyncClient) -> None:
    """API-STAR-01 — a starred item that is trashed must not keep showing."""
    h = auth_headers(await register_and_login(client, email="star-trash@test.com"))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Doomed"}, headers=h)
    item_id = folder.json()["id"]
    await _star(client, h, item_id)
    assert item_id in await _starred_ids(client, h)

    trash = await client.post(f"/api/v1/trash/items/{item_id}", headers=h)
    assert trash.status_code in (200, 204), trash.text

    assert item_id not in await _starred_ids(client, h)


async def test_recent_is_replayed_from_activity_not_from_updated_at(client: AsyncClient) -> None:
    """API-RECENT-01.

    Starring is the clean discriminator: it writes a STAR row to activity_logs
    but does *not* touch drive_items.updated_at (it lives in
    user_item_preferences). So if Recent were sorted by updated_at the newest
    *created* item would lead; only an activity-driven list puts the older,
    just-starred item first.
    """
    h = auth_headers(await register_and_login(client, email="recent@test.com"))

    older = await client.post("/api/v1/drive/folders", json={"name": "Older"}, headers=h)
    older_id = older.json()["id"]
    newer = await client.post("/api/v1/drive/folders", json={"name": "Newer"}, headers=h)
    newer_id = newer.json()["id"]

    # Touch the *older* item last, without changing its updated_at.
    await _star(client, h, older_id)

    resp = await client.get("/api/v1/drive/recent", headers=h)
    assert resp.status_code == 200, resp.text
    order = [i["id"] for i in resp.json()]

    assert older_id in order and newer_id in order
    assert order.index(older_id) < order.index(newer_id), (
        "Recent must be derived from activity_logs; this ordering means it fell "
        "back to drive_items.updated_at"
    )


async def test_recent_excludes_trashed_items(client: AsyncClient) -> None:
    """API-RECENT-01 — activity rows outlive the item, the listing must not."""
    h = auth_headers(await register_and_login(client, email="recent-trash@test.com"))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Ghost"}, headers=h)
    item_id = folder.json()["id"]

    before = await client.get("/api/v1/drive/recent", headers=h)
    assert item_id in [i["id"] for i in before.json()]

    await client.post(f"/api/v1/trash/items/{item_id}", headers=h)

    after = await client.get("/api/v1/drive/recent", headers=h)
    assert item_id not in [i["id"] for i in after.json()]
