from __future__ import annotations

import io

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def test_share_with_user_appears_in_shared_with_me(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="owner@test.com", username="owner")
    token_b = await register_and_login(client, email="guest@test.com", username="guest")

    folder = await client.post(
        "/api/v1/drive/folders",
        json={"name": "SharedFolder"},
        headers=auth_headers(token_a),
    )
    item_id = folder.json()["id"]

    share = await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": "guest@test.com", "permission": "viewer"},
        headers=auth_headers(token_a),
    )
    assert share.status_code == 201
    assert share.json()["permission"] == "viewer"

    # Guest should see it in shared-with-me
    shared = await client.get("/api/v1/share/shared-with-me", headers=auth_headers(token_b))
    assert shared.status_code == 200
    item_ids = [s["item_id"] for s in shared.json()["items"]]
    assert item_id in item_ids


async def test_permission_isolation_owner_only_download(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="owner2@test.com", username="owner2")
    token_b = await register_and_login(client, email="stranger@test.com", username="stranger")

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=auth_headers(token_a),
        files={"file": ("private.txt", io.BytesIO(b"private content"), "text/plain")},
    )
    item_id = upload.json()["id"]

    # Stranger without share cannot download
    resp = await client.get(f"/api/v1/download/{item_id}", headers=auth_headers(token_b))
    assert resp.status_code in (403, 404)

    # Owner can download
    owner_resp = await client.get(f"/api/v1/download/{item_id}", headers=auth_headers(token_a))
    assert owner_resp.status_code == 200


async def test_remove_share_stops_access(client: AsyncClient) -> None:
    token_a = await register_and_login(client, email="sharer@test.com", username="sharer")
    token_b = await register_and_login(client, email="revoked@test.com", username="revoked")

    folder = await client.post(
        "/api/v1/drive/folders",
        json={"name": "TempShared"},
        headers=auth_headers(token_a),
    )
    item_id = folder.json()["id"]

    share = await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": "revoked@test.com", "permission": "viewer"},
        headers=auth_headers(token_a),
    )
    target_user_id = share.json()["target_user_id"]

    # Confirm share is present
    shared = await client.get("/api/v1/share/shared-with-me", headers=auth_headers(token_b))
    assert any(s["item_id"] == item_id for s in shared.json()["items"])

    # Remove share
    remove = await client.delete(
        f"/api/v1/share/items/{item_id}/users/{target_user_id}",
        headers=auth_headers(token_a),
    )
    assert remove.status_code == 204

    # Confirm share is gone
    shared_after = await client.get("/api/v1/share/shared-with-me", headers=auth_headers(token_b))
    assert not any(s["item_id"] == item_id for s in shared_after.json()["items"])


async def test_create_share_link(client: AsyncClient) -> None:
    token = await register_and_login(client, email="linker@test.com", username="linker")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "LinkFolder"}, headers=h)
    item_id = folder.json()["id"]

    link_resp = await client.post(
        f"/api/v1/share/items/{item_id}/links",
        json={"permission": "viewer"},
        headers=h,
    )
    assert link_resp.status_code == 201
    link = link_resp.json()
    assert link["is_active"] is True
    assert link["permission"] == "viewer"
    assert "token" in link


async def test_deactivate_share_link(client: AsyncClient) -> None:
    token = await register_and_login(client, email="deactivate@test.com", username="deact")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "DeactFolder"}, headers=h)
    item_id = folder.json()["id"]

    link = await client.post(
        f"/api/v1/share/items/{item_id}/links", json={"permission": "viewer"}, headers=h
    )
    link_id = link.json()["id"]
    link_token = link.json()["token"]

    deact = await client.delete(f"/api/v1/share/links/{link_id}", headers=h)
    assert deact.status_code == 204

    # Opening the deactivated link as a guest must fail (§28.5 criterion 4).
    opened = await client.post(f"/api/v1/public/links/{link_token}/session", json={})
    assert opened.status_code == 404
    assert opened.json()["error"]["code"] == "SHARE_LINK_INVALID"


async def test_editor_can_modify_shared_item(client: AsyncClient) -> None:
    """A share granting `editor` must actually allow editing.

    Regression: drive operations compared `owner_id` directly and ignored
    shares entirely, so an editor could view/download but never rename or
    move — the tier was effectively dead (detailed-design §6.5 grants
    rename/move/create-folder to "owner or editor").
    """
    owner = auth_headers(await register_and_login(client, email="ed-owner@test.com"))
    editor_email = "ed-editor@test.com"
    editor = auth_headers(await register_and_login(client, email=editor_email))

    folder = await client.post("/api/v1/drive/folders", json={"name": "Team"}, headers=owner)
    folder_id = folder.json()["id"]
    upload = await client.post(
        "/api/v1/upload/simple",
        headers=owner,
        params={"parent_id": folder_id},
        files={"file": ("notes.txt", io.BytesIO(b"team notes"), "text/plain")},
    )
    item_id = upload.json()["id"]

    shared = await client.post(
        f"/api/v1/share/items/{folder_id}",
        json={"target_email": editor_email, "permission": "editor"},
        headers=owner,
    )
    assert shared.status_code == 201

    # Editor may rename, create a folder inside, and move — all previously 403.
    renamed = await client.patch(
        f"/api/v1/drive/items/{item_id}/name", json={"name": "edited.txt"}, headers=editor
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["name"] == "edited.txt"

    sub = await client.post(
        "/api/v1/drive/folders", json={"name": "Sub", "parent_id": folder_id}, headers=editor
    )
    assert sub.status_code == 201, sub.text

    moved = await client.patch(
        f"/api/v1/drive/items/{item_id}/parent",
        json={"parent_id": sub.json()["id"]},
        headers=editor,
    )
    assert moved.status_code == 200, moved.text


async def test_viewer_cannot_modify_shared_item(client: AsyncClient) -> None:
    """Honouring shares must not over-grant: viewer stays read-only."""
    owner = auth_headers(await register_and_login(client, email="vw-owner@test.com"))
    viewer_email = "vw-viewer@test.com"
    viewer = auth_headers(await register_and_login(client, email=viewer_email))

    upload = await client.post(
        "/api/v1/upload/simple",
        headers=owner,
        files={"file": ("readonly.txt", io.BytesIO(b"look only"), "text/plain")},
    )
    item_id = upload.json()["id"]
    await client.post(
        f"/api/v1/share/items/{item_id}",
        json={"target_email": viewer_email, "permission": "viewer"},
        headers=owner,
    )

    renamed = await client.patch(
        f"/api/v1/drive/items/{item_id}/name", json={"name": "nope.txt"}, headers=viewer
    )
    assert renamed.status_code == 403
    # Viewing is still allowed.
    assert (await client.get(f"/api/v1/drive/items/{item_id}", headers=viewer)).status_code == 200


# ── Shared by me (proposal §29) ──────────────────────────────────────────────


async def test_shared_by_me_aggregates_and_badges_the_drive_listing(
    client: AsyncClient,
) -> None:
    """The reverse view plus the My Drive markers, against real SQL.

    The grouping and the badge query are pure repository work, so the in-memory
    fakes cannot vouch for them.
    """
    owner = await register_and_login(client, email="sbm-owner@test.com", username="sbmowner")
    h = auth_headers(owner)
    for i in range(2):
        await register_and_login(client, email=f"sbm-friend{i}@test.com", username=f"sbmfriend{i}")

    deck = (await client.post("/api/v1/drive/folders", json={"name": "Deck"}, headers=h)).json()
    # Never shared — the control case for both the listing and the badges.
    await client.post("/api/v1/drive/folders", json={"name": "Private"}, headers=h)
    linked = (await client.post("/api/v1/drive/folders", json={"name": "Linked"}, headers=h)).json()

    for i in range(2):
        resp = await client.post(
            f"/api/v1/share/items/{deck['id']}",
            json={"target_email": f"sbm-friend{i}@test.com", "permission": "viewer"},
            headers=h,
        )
        assert resp.status_code == 201, resp.text
    await client.post(
        f"/api/v1/share/items/{deck['id']}/links",
        json={"permission": "viewer", "password": "pw"},
        headers=h,
    )
    await client.post(
        f"/api/v1/share/items/{linked['id']}/links",
        json={"permission": "downloader"},
        headers=h,
    )

    listed = await client.get("/api/v1/share/shared-by-me", headers=h)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    by_name = {e["item"]["name"]: e for e in body["items"]}

    assert body["total"] == 2  # Private is not listed at all
    assert "Private" not in by_name
    # Two people plus a link on one item is a single entry (§29.3 criterion 4).
    assert len(by_name["Deck"]["user_shares"]) == 2
    assert len(by_name["Deck"]["links"]) == 1
    assert by_name["Deck"]["links"][0]["has_password"] is True
    assert "pw" not in listed.text and "password_hash" not in listed.text
    assert {u["email"] for u in by_name["Deck"]["user_shares"]} == {
        "sbm-friend0@test.com",
        "sbm-friend1@test.com",
    }

    # My Drive markers: the two kinds of sharing stay distinguishable.
    drive = await client.get("/api/v1/drive/items", headers=h)
    flags = {
        i["name"]: (i["is_shared_with_users"], i["has_active_public_link"])
        for i in drive.json()["items"]
    }
    assert flags["Deck"] == (True, True)
    assert flags["Linked"] == (False, True)
    assert flags["Private"] == (False, False)


async def test_shared_by_me_drops_trashed_items_and_marks_dead_links(
    client: AsyncClient,
) -> None:
    owner = await register_and_login(client, email="sbm-trash@test.com", username="sbmtrash")
    h = auth_headers(owner)
    gone = (await client.post("/api/v1/drive/folders", json={"name": "Gone"}, headers=h)).json()
    kept = (await client.post("/api/v1/drive/folders", json={"name": "Kept"}, headers=h)).json()

    await client.post(
        f"/api/v1/share/items/{gone['id']}/links", json={"permission": "viewer"}, headers=h
    )
    created = await client.post(
        f"/api/v1/share/items/{kept['id']}/links", json={"permission": "viewer"}, headers=h
    )
    await client.post(f"/api/v1/trash/items/{gone['id']}", headers=h)
    await client.delete(f"/api/v1/share/links/{created.json()['id']}", headers=h)

    body = (await client.get("/api/v1/share/shared-by-me", headers=h)).json()
    names = [e["item"]["name"] for e in body["items"]]

    assert names == ["Kept"]  # trashed item disappears from the view
    # The disabled link stays visible so the owner knows it once existed.
    assert body["items"][0]["links"][0]["is_active"] is False
    assert body["items"][0]["item"]["has_active_public_link"] is False


async def test_removing_a_link_revokes_it_and_clears_the_row(client: AsyncClient) -> None:
    """One action, not two (proposal §29.5 decision 4, revised 2026-07-27)."""
    owner = await register_and_login(client, email="sbm-clear@test.com", username="sbmclear")
    h = auth_headers(owner)
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "Cleanup"}, headers=h)
    ).json()
    created = await client.post(
        f"/api/v1/share/items/{folder['id']}/links", json={"permission": "viewer"}, headers=h
    )
    link_id = created.json()["id"]
    guest_token = created.json()["token"]

    # Removing a live link is allowed and is itself the revocation.
    assert (
        await client.delete(f"/api/v1/share/links/{link_id}/record", headers=h)
    ).status_code == 204

    # The guest side stops working straight away — the token no longer resolves.
    opened = await client.post(f"/api/v1/public/links/{guest_token}/session", json={})
    assert opened.status_code == 404

    # With its only share gone, the item drops out of the view entirely.
    assert (await client.get("/api/v1/share/shared-by-me", headers=h)).json()["items"] == []
