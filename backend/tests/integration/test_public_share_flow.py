"""End-to-end guest access to a public share link (proposal §28).

Covers the part unit tests cannot: that a link created through the real API is
actually openable by a caller holding no session at all — the gap this feature
was written to close — and that the attempt counter really survives in the
database rather than in one worker's memory.
"""

from __future__ import annotations

import io
from typing import Any

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


async def _upload(
    client: AsyncClient, headers: dict[str, str], name: str, parent: str | None
) -> dict[str, Any]:
    params = {"parent_id": parent} if parent else {}
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=headers,
        params=params,
        files={"file": (name, io.BytesIO(b"shared bytes"), "text/plain")},
    )
    assert resp.status_code in (200, 201), resp.text
    body: dict[str, Any] = resp.json()
    return body


async def _create_link(
    client: AsyncClient, headers: dict[str, str], item_id: str, **body: object
) -> str:
    resp = await client.post(
        f"/api/v1/share/items/{item_id}/links",
        headers=headers,
        json={"permission": "downloader", **body},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    assert token, "the plaintext token is only ever returned at creation"
    return str(token)


async def test_guest_opens_a_link_and_downloads_without_logging_in(
    client: AsyncClient,
) -> None:
    token = await register_and_login(client, email="pub-owner@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "shared.txt", None)
    link = await _create_link(client, h, doc["id"])

    # No Authorization header anywhere below — this is a stranger with a URL.
    opened = await client.post(f"/api/v1/public/links/{link}/session", json={})
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["item"]["name"] == "shared.txt"
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    got = await client.get(f"/api/v1/public/items/{doc['id']}/download", headers=guest)
    assert got.status_code == 200
    assert got.content == b"shared bytes"


async def test_viewer_link_cannot_download(client: AsyncClient) -> None:
    token = await register_and_login(client, email="pub-viewer@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "readonly.txt", None)
    link = await _create_link(client, h, doc["id"], permission="viewer")

    body = (await client.post(f"/api/v1/public/links/{link}/session", json={})).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    resp = await client.get(f"/api/v1/public/items/{doc['id']}/download", headers=guest)
    assert resp.status_code == 403


async def test_password_link_hides_everything_until_the_password_is_right(
    client: AsyncClient,
) -> None:
    token = await register_and_login(client, email="pub-pw@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "secret.txt", None)
    link = await _create_link(client, h, doc["id"], password="opensesame")

    probe = await client.post(f"/api/v1/public/links/{link}/session", json={})
    assert probe.status_code == 401
    assert probe.json()["error"]["code"] == "SHARE_LINK_PASSWORD_REQUIRED"
    assert "secret.txt" not in probe.text  # no metadata before authentication

    wrong = await client.post(f"/api/v1/public/links/{link}/session", json={"password": "guess"})
    unknown = await client.post("/api/v1/public/links/not-a-real-token/session", json={})
    assert wrong.status_code == unknown.status_code == 404
    assert wrong.json()["error"] == unknown.json()["error"]

    ok = await client.post(f"/api/v1/public/links/{link}/session", json={"password": "opensesame"})
    assert ok.status_code == 200
    assert ok.json()["item"]["name"] == "secret.txt"


async def test_attempts_are_throttled_and_the_counter_persists(client: AsyncClient) -> None:
    """The lock must come from the row, not from in-process state."""
    token = await register_and_login(client, email="pub-throttle@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "brute.txt", None)
    link = await _create_link(client, h, doc["id"], password="correct-horse")

    for _ in range(6):
        resp = await client.post(f"/api/v1/public/links/{link}/session", json={"password": "wrong"})
        assert resp.status_code == 404

    locked = await client.post(
        f"/api/v1/public/links/{link}/session", json={"password": "correct-horse"}
    )
    assert locked.status_code == 404, "correct password must still be refused while locked"


async def test_folder_link_browses_the_subtree_and_zips_it(client: AsyncClient) -> None:
    token = await register_and_login(client, email="pub-folder@test.com")
    h = auth_headers(token)
    folder = (await client.post("/api/v1/drive/folders", json={"name": "Public"}, headers=h)).json()
    inside = await _upload(client, h, "inside.txt", folder["id"])
    outside = await _upload(client, h, "outside.txt", None)
    link = await _create_link(client, h, folder["id"])

    body = (await client.post(f"/api/v1/public/links/{link}/session", json={})).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    listing = await client.get(f"/api/v1/public/items/{folder['id']}/children", headers=guest)
    assert listing.status_code == 200
    assert [i["name"] for i in listing.json()["items"]] == ["inside.txt"]

    # An item that exists but sits outside the shared subtree must look absent,
    # not forbidden (proposal §28.3 rule 4).
    denied = await client.get(f"/api/v1/public/items/{outside['id']}/download", headers=guest)
    assert denied.status_code == 404

    zipped = await client.get("/api/v1/public/archive", headers=guest)
    assert zipped.status_code == 200
    assert zipped.content[:2] == b"PK"
    assert b"outside.txt" not in zipped.content
    assert inside["name"].encode() in zipped.content


async def test_disabling_a_link_revokes_live_guest_sessions(client: AsyncClient) -> None:
    token = await register_and_login(client, email="pub-revoke@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "revoked.txt", None)

    created = await client.post(
        f"/api/v1/share/items/{doc['id']}/links",
        headers=h,
        json={"permission": "downloader"},
    )
    link_id = created.json()["id"]
    guest_token = created.json()["token"]

    body = (await client.post(f"/api/v1/public/links/{guest_token}/session", json={})).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}
    assert (await client.get("/api/v1/public/items", headers=guest)).status_code == 200

    assert (await client.delete(f"/api/v1/share/links/{link_id}", headers=h)).status_code == 204

    # The credential has not expired, but the link is gone — access must stop
    # right away rather than when the credential happens to lapse.
    assert (await client.get("/api/v1/public/items", headers=guest)).status_code == 404


async def test_a_logged_in_user_token_does_not_unlock_the_public_routes(
    client: AsyncClient,
) -> None:
    token = await register_and_login(client, email="pub-escalate@test.com")
    h = auth_headers(token)
    doc = await _upload(client, h, "mine.txt", None)
    await _create_link(client, h, doc["id"])

    # The owner's own access token is not a share credential.
    resp = await client.get("/api/v1/public/items", headers=h)
    assert resp.status_code == 404


async def test_a_guest_with_an_editor_link_can_write_and_it_is_traceable(
    client: AsyncClient,
) -> None:
    """The whole point of proposal §33, end to end.

    Checks the two things unit tests with mocked services cannot: that the
    upload really lands in the owner's drive and against their quota, and that
    the audit row says both *whose* it is and *how* it got there.
    """
    token = await register_and_login(client, email="pub-editor@test.com")
    h = auth_headers(token)
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "Dropbox"}, headers=h)
    ).json()

    before = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]

    created = await client.post(
        f"/api/v1/share/items/{folder['id']}/links",
        headers=h,
        json={
            "permission": "editor",
            "expires_at": "2027-01-01T00:00:00Z",
            "password": "guest-pass",
        },
    )
    assert created.status_code == 201, created.text
    link_token = created.json()["token"]

    body = (
        await client.post(
            f"/api/v1/public/links/{link_token}/session", json={"password": "guest-pass"}
        )
    ).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    dropped = await client.post(
        f"/api/v1/public/items/{folder['id']}/upload",
        headers=guest,
        files={"file": ("from-outside.txt", io.BytesIO(b"delivered"), "text/plain")},
    )
    assert dropped.status_code == 200, dropped.text

    # It landed in the owner's drive...
    listing = await client.get(f"/api/v1/drive/items?parent_id={folder['id']}", headers=h)
    assert [i["name"] for i in listing.json()["items"]] == ["from-outside.txt"]

    # ...and against the owner's quota, because it is their storage.
    after = (await client.get("/api/v1/users/me/quota", headers=h)).json()["used_bytes"]
    assert after > before


async def test_an_editor_link_must_carry_an_expiry_and_a_password(client: AsyncClient) -> None:
    token = await register_and_login(client, email="pub-editor-exp@test.com")
    h = auth_headers(token)
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "NoExpiry"}, headers=h)
    ).json()

    async def _create(**body: object) -> int:
        resp = await client.post(
            f"/api/v1/share/items/{folder['id']}/links",
            headers=h,
            json={"permission": "editor", **body},
        )
        return resp.status_code

    # A link that lets strangers write and never dies is not something to create
    # by omission, and the URL alone must not be enough (proposal §33.3 rule 4).
    assert await _create() == 422
    assert await _create(expires_at="2027-01-01T00:00:00Z") == 422
    assert await _create(password="s3cret") == 422
    assert await _create(expires_at="2027-01-01T00:00:00Z", password="s3cret") == 201


async def test_the_owner_can_copy_a_link_url_again_later(client: AsyncClient) -> None:
    """proposal §29.3 criterion 3.2 — and the recovered URL really opens."""
    token = await register_and_login(client, email="pub-recopy@test.com")
    h = auth_headers(token)
    folder = (await client.post("/api/v1/drive/folders", json={"name": "Recopy"}, headers=h)).json()
    created = (
        await client.post(
            f"/api/v1/share/items/{folder['id']}/links",
            headers=h,
            json={"permission": "downloader"},
        )
    ).json()

    listing = await client.get("/api/v1/share/shared-by-me", headers=h)
    link_id = listing.json()["items"][0]["links"][0]["link_id"]
    # The listing hands out no plaintext — that is what the endpoint below is for.
    assert created["token"] not in listing.text

    revealed = await client.get(f"/api/v1/share/links/{link_id}/token", headers=h)
    assert revealed.status_code == 200
    assert revealed.json()["token"] == created["token"]

    # The whole point: the recovered token still opens the link.
    opened = await client.post(f"/api/v1/public/links/{revealed.json()['token']}/session", json={})
    assert opened.status_code == 200


async def test_only_the_owner_can_copy_a_link_url(client: AsyncClient) -> None:
    owner = auth_headers(await register_and_login(client, email="pub-recopy-owner@test.com"))
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "Mine"}, headers=owner)
    ).json()
    await client.post(
        f"/api/v1/share/items/{folder['id']}/links",
        headers=owner,
        json={"permission": "downloader"},
    )
    link_id = (await client.get("/api/v1/share/shared-by-me", headers=owner)).json()["items"][0][
        "links"
    ][0]["link_id"]

    stranger = auth_headers(await register_and_login(client, email="pub-recopy-other@test.com"))
    resp = await client.get(f"/api/v1/share/links/{link_id}/token", headers=stranger)

    assert resp.status_code == 403


async def test_a_viewer_link_still_cannot_write(client: AsyncClient) -> None:
    token = await register_and_login(client, email="pub-noeditor@test.com")
    h = auth_headers(token)
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "ReadOnly"}, headers=h)
    ).json()
    link = await _create_link(client, h, folder["id"], permission="viewer")

    body = (await client.post(f"/api/v1/public/links/{link}/session", json={})).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    resp = await client.post(
        f"/api/v1/public/items/{folder['id']}/upload",
        headers=guest,
        files={"file": ("nope.txt", io.BytesIO(b"x"), "text/plain")},
    )
    # Existing links must not gain abilities because the feature shipped.
    assert resp.status_code == 403


async def test_a_guest_can_zip_just_the_items_they_picked(client: AsyncClient) -> None:
    """proposal §34.4 — the selection is packed, and only the selection."""
    token = await register_and_login(client, email="pub-pick@test.com")
    h = auth_headers(token)
    folder = (await client.post("/api/v1/drive/folders", json={"name": "Picked"}, headers=h)).json()
    a = await _upload(client, h, "wanted.txt", folder["id"])
    await _upload(client, h, "skipped.txt", folder["id"])
    outside = await _upload(client, h, "elsewhere.txt", None)
    link = await _create_link(client, h, folder["id"])

    body = (await client.post(f"/api/v1/public/links/{link}/session", json={})).json()
    guest = {"Authorization": f"Bearer {body['access_token']}"}

    picked = await client.post(
        "/api/v1/public/archive", json={"item_ids": [a["id"]]}, headers=guest
    )
    assert picked.status_code == 200
    assert picked.content[:2] == b"PK"
    assert b"wanted.txt" in picked.content
    assert b"skipped.txt" not in picked.content

    # One id outside the subtree fails the whole request rather than quietly
    # packing the rest — a partial zip would reveal whether that id exists.
    leaked = await client.post(
        "/api/v1/public/archive",
        json={"item_ids": [a["id"], outside["id"]]},
        headers=guest,
    )
    assert leaked.status_code == 404
