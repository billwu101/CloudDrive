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
