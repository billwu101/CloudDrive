"""Renewal of a guest's short-lived share credential (API-PUB-14).

Covers ``POST /public/links/{token}/session/refresh`` — proposal §28.7 decision
1, design §6.12.8 and its testable item 9 — which had no integration coverage at
all. Every request below is made with **no user session**: the only credential
in play is the share access token a guest exchanged their link for.

The endpoint exists so a guest can keep browsing past the 15-minute credential
window without the frontend having to keep the link password around
(proposal §28.3 rule 3). That makes two properties load-bearing, and both are
asserted here rather than assumed:

* renewal only *extends* a state the caller already earned — it never
  re-authorises, so a link that has since been deleted, disabled or expired must
  stop renewals immediately (proposal §28.3 rule 5), and it must not hand back
  more permission than the link currently grants (rule 4);
* every way it can fail answers identically, so the endpoint cannot be turned
  into an oracle for which links exist (proposal §28.3 rule 1).

A few tests mint a credential directly with ``create_share_access_token`` for a
link that was created through the real API. That is the only way to reach the
240-minute total-lifetime cap and the chain-start behaviour without freezing the
clock or sleeping for four hours; the link, the item and every request under
test are still the real ones.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient, Response

from app.core.config import get_settings
from app.core.security import create_share_access_token, decode_share_access_token
from app.models.share_link import ShareLink
from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


# --- helpers -----------------------------------------------------------------


async def _upload(
    client: AsyncClient, headers: dict[str, str], name: str, parent: str | None
) -> dict[str, Any]:
    params = {"parent_id": parent} if parent else {}
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=headers,
        params=params,
        files={"file": (name, io.BytesIO(b"renewable bytes"), "text/plain")},
    )
    assert resp.status_code in (200, 201), resp.text
    body: dict[str, Any] = resp.json()
    return body


async def _create_link(
    client: AsyncClient, headers: dict[str, str], item_id: str, **body: object
) -> dict[str, Any]:
    """Create a link and return the whole creation body (id *and* plaintext token)."""
    resp = await client.post(
        f"/api/v1/share/items/{item_id}/links",
        headers=headers,
        json={"permission": "downloader", **body},
    )
    assert resp.status_code == 201, resp.text
    created: dict[str, Any] = resp.json()
    assert created["token"], "the plaintext token is only ever returned at creation"
    return created


async def _open(client: AsyncClient, token: str, password: str | None = None) -> dict[str, Any]:
    body = {"password": password} if password is not None else {}
    resp = await client.post(f"/api/v1/public/links/{token}/session", json=body)
    assert resp.status_code == 200, resp.text
    opened: dict[str, Any] = resp.json()
    return opened


def _guest(credential: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {credential}"}


async def _refresh(client: AsyncClient, path_token: str, credential: str) -> Response:
    return await client.post(
        f"/api/v1/public/links/{path_token}/session/refresh",
        headers=_guest(credential),
    )


async def _expire_link(link_id: str) -> None:
    """Backdate a link's expiry in the database.

    There is no API for this: expiry is set at creation and only time moves it.
    Writing the row directly is what keeps the expiry test deterministic instead
    of sleeping past a near-future expiry.
    """
    async with _SessionFactory() as session:
        link = await session.get(ShareLink, UUID(link_id))
        assert link is not None
        link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        await session.commit()


def _links_for(listing: dict[str, Any], item_id: str) -> list[dict[str, Any]]:
    return [
        link
        for entry in listing["items"]
        if entry["item"]["id"] == item_id
        for link in entry["links"]
    ]


# --- the credential renewal actually works -----------------------------------


async def test_refreshing_hands_back_a_credential_that_really_opens_the_content(
    client: AsyncClient,
) -> None:
    """API-PUB-14 — proposal §28.7 decision 1.

    The renewed credential is verified by *using* it on the read endpoints, not
    by trusting the refresh response: a token that parses but no longer opens
    anything would defeat the whole point of the endpoint.
    """
    settings = get_settings()
    h = auth_headers(await register_and_login(client, email="pub-refresh-ok@test.com"))
    doc = await _upload(client, h, "renewed.txt", None)
    link = await _create_link(client, h, doc["id"])

    first = await _open(client, link["token"])
    resp = await _refresh(client, link["token"], first["access_token"])

    assert resp.status_code == 200, resp.text
    renewed = resp.json()
    assert renewed["access_token"] != first["access_token"], "a refresh must mint a new credential"
    assert renewed["permission"] == "downloader"
    assert renewed["expires_in"] == settings.share_access_token_expire_minutes * 60
    assert renewed["item"]["id"] == doc["id"]
    assert renewed["item"]["name"] == "renewed.txt"

    # Read back through separate endpoints with the *new* credential only.
    guest = _guest(renewed["access_token"])
    root = await client.get("/api/v1/public/items", headers=guest)
    assert root.status_code == 200, root.text
    assert root.json()["id"] == doc["id"]

    got = await client.get(f"/api/v1/public/items/{doc['id']}/download", headers=guest)
    assert got.status_code == 200, got.text
    assert got.content == b"renewable bytes"


async def test_refreshing_a_password_protected_link_never_asks_for_the_password_again(
    client: AsyncClient,
) -> None:
    """proposal §28.3 rule 3, design §6.12.8 — the reason this endpoint exists.

    The refresh request carries no body at all, so the frontend has nowhere to
    keep the password. What must *not* follow is that renewal became a way in:
    a fresh visitor still hits the password gate.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-pw@test.com"))
    doc = await _upload(client, h, "guarded.txt", None)
    link = await _create_link(client, h, doc["id"], password="opensesame")

    first = await _open(client, link["token"], password="opensesame")
    resp = await _refresh(client, link["token"], first["access_token"])

    assert resp.status_code == 200, resp.text
    guest = _guest(resp.json()["access_token"])
    got = await client.get(f"/api/v1/public/items/{doc['id']}/download", headers=guest)
    assert got.status_code == 200
    assert got.content == b"renewable bytes"

    # A newcomer with only the URL is still stopped at the password.
    cold = await client.post(f"/api/v1/public/links/{link['token']}/session", json={})
    assert cold.status_code == 401
    assert cold.json()["error"]["code"] == "SHARE_LINK_PASSWORD_REQUIRED"


# --- the chain, and the cap on it --------------------------------------------


async def test_refreshing_carries_the_original_chain_start_instead_of_restarting_it(
    client: AsyncClient,
) -> None:
    """design §6.12.8 — the mechanism behind testable item 9.

    Renewal must not reset the clock it is capped against, otherwise a client
    that refreshes every fourteen minutes would live forever. Started from a
    credential minted an hour ago so that a reset would be unmistakable: a
    genuinely restarted chain would read as "just now".
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-chain@test.com"))
    doc = await _upload(client, h, "chained.txt", None)
    link = await _create_link(client, h, doc["id"])

    started = datetime.now(UTC) - timedelta(minutes=60)
    aged = create_share_access_token(
        link_id=UUID(link["id"]),
        root_item_id=UUID(doc["id"]),
        permission="downloader",
        chain_started_at=started,
    )

    once = await _refresh(client, link["token"], aged)
    assert once.status_code == 200, once.text
    twice = await _refresh(client, link["token"], once.json()["access_token"])
    assert twice.status_code == 200, twice.text

    for label, issued in (("first", once), ("second", twice)):
        claims = decode_share_access_token(issued.json()["access_token"])
        drift = abs((claims.chain_started_at - started).total_seconds())
        assert drift < 1, f"{label} refresh moved the chain start by {drift}s"
        assert claims.link_id == UUID(link["id"])
        assert claims.permission == "downloader"

    # The twice-renewed credential is still a working one.
    root = await client.get("/api/v1/public/items", headers=_guest(twice.json()["access_token"]))
    assert root.status_code == 200
    assert root.json()["id"] == doc["id"]


async def test_refreshing_stops_once_the_total_lifetime_cap_is_passed(
    client: AsyncClient,
) -> None:
    """design §6.12.8 testable item 9 — refresh cannot outrun the cap.

    Both sides of the boundary are exercised against the same live link, so a
    404 here can only be the cap and not some unrelated refusal.
    """
    cap = get_settings().share_access_token_max_lifetime_minutes
    h = auth_headers(await register_and_login(client, email="pub-refresh-cap@test.com"))
    doc = await _upload(client, h, "capped.txt", None)
    link = await _create_link(client, h, doc["id"])

    def _credential_started(minutes_ago: int) -> str:
        return create_share_access_token(
            link_id=UUID(link["id"]),
            root_item_id=UUID(doc["id"]),
            permission="downloader",
            chain_started_at=datetime.now(UTC) - timedelta(minutes=minutes_ago),
        )

    inside = await _refresh(client, link["token"], _credential_started(cap - 10))
    assert inside.status_code == 200, inside.text
    assert inside.json()["item"]["id"] == doc["id"]

    outside = await _refresh(client, link["token"], _credential_started(cap + 10))
    assert outside.status_code == 404, outside.text
    assert outside.json()["error"]["code"] == "SHARE_LINK_INVALID"


# --- the link's current state governs every renewal --------------------------


async def test_refreshing_fails_once_the_owner_deletes_the_link(client: AsyncClient) -> None:
    """API-PUB-04 / API-PUB-12 — proposal §28.3 rule 5, §29.5 decision 4.

    The first refresh is a control: it proves the credential and the endpoint
    were working right up to the deletion, so the second refusal is the deletion
    and nothing else.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-del@test.com"))
    doc = await _upload(client, h, "doomed.txt", None)
    link = await _create_link(client, h, doc["id"])

    first = await _open(client, link["token"])
    control = await _refresh(client, link["token"], first["access_token"])
    assert control.status_code == 200, control.text
    live_credential = control.json()["access_token"]

    gone = await client.delete(f"/api/v1/share/links/{link['id']}/record", headers=h)
    assert gone.status_code == 204, gone.text

    # The credential itself has not expired — the link behind it is simply gone.
    after = await _refresh(client, link["token"], live_credential)
    assert after.status_code == 404, after.text
    assert after.json()["error"]["code"] == "SHARE_LINK_INVALID"

    # Reads stop at the same moment, and the URL no longer opens a new session.
    read = await client.get("/api/v1/public/items", headers=_guest(live_credential))
    assert read.status_code == 404
    reopened = await client.post(f"/api/v1/public/links/{link['token']}/session", json={})
    assert reopened.status_code == 404

    # The owner's own view agrees the record is gone, not merely disabled.
    listing = await client.get("/api/v1/share/shared-by-me", headers=h)
    assert _links_for(listing.json(), doc["id"]) == []


async def test_refreshing_fails_once_the_owner_disables_the_link(client: AsyncClient) -> None:
    """API-PUB-12 — proposal §28.3 rule 5, the disable path rather than delete.

    Distinct from deletion: the row survives and the owner can still see it, so
    this checks the refusal comes from `is_active`, not from a missing row.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-off@test.com"))
    doc = await _upload(client, h, "switched-off.txt", None)
    link = await _create_link(client, h, doc["id"])

    first = await _open(client, link["token"])
    control = await _refresh(client, link["token"], first["access_token"])
    assert control.status_code == 200, control.text
    live_credential = control.json()["access_token"]

    disabled = await client.delete(f"/api/v1/share/links/{link['id']}", headers=h)
    assert disabled.status_code == 204, disabled.text

    after = await _refresh(client, link["token"], live_credential)
    assert after.status_code == 404, after.text
    assert after.json()["error"]["code"] == "SHARE_LINK_INVALID"
    assert (
        await client.get("/api/v1/public/items", headers=_guest(live_credential))
    ).status_code == 404

    listing = await client.get("/api/v1/share/shared-by-me", headers=h)
    rows = _links_for(listing.json(), doc["id"])
    assert len(rows) == 1, "disabling keeps the record so the owner can still see it"
    assert rows[0]["link_id"] == link["id"]
    assert rows[0]["is_active"] is False


async def test_refreshing_fails_once_the_link_has_expired(client: AsyncClient) -> None:
    """API-PUB-05 — proposal §28.3 rule 5, §28.5 criterion 4.

    An expiry that has passed must end renewals too, otherwise a guest holding a
    credential at the moment of expiry could keep renewing indefinitely and the
    expiry date would mean nothing.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-exp@test.com"))
    doc = await _upload(client, h, "timed.txt", None)
    expires = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    link = await _create_link(client, h, doc["id"], expires_at=expires)

    first = await _open(client, link["token"])
    control = await _refresh(client, link["token"], first["access_token"])
    assert control.status_code == 200, control.text
    live_credential = control.json()["access_token"]

    await _expire_link(link["id"])

    after = await _refresh(client, link["token"], live_credential)
    assert after.status_code == 404, after.text
    assert after.json()["error"]["code"] == "SHARE_LINK_INVALID"
    assert (
        await client.get("/api/v1/public/items", headers=_guest(live_credential))
    ).status_code == 404
    assert (
        await client.post(f"/api/v1/public/links/{link['token']}/session", json={})
    ).status_code == 404

    listing = await client.get("/api/v1/share/shared-by-me", headers=h)
    rows = _links_for(listing.json(), doc["id"])
    assert len(rows) == 1
    assert rows[0]["is_active"] is False, "an expired link reads as inactive to its owner"


# --- failures must not be tellable apart -------------------------------------


async def test_every_way_a_refresh_can_fail_answers_identically(client: AsyncClient) -> None:
    """API-PUB-06 — proposal §28.3 rule 1, §28.5 criterion 5.

    A credential naming a link that never existed, one whose link was deleted,
    one whose link expired, a user's own access token and outright garbage must
    all produce the same status and the same body. Any difference between them
    is a way to ask the server which links exist.

    Also covers the cross-token case: the path segment must never stand in for
    the credential, so a dead link's credential presented at a live link's
    refresh URL still fails.
    """
    owner_token = await register_and_login(client, email="pub-refresh-same@test.com")
    h = auth_headers(owner_token)
    live_doc = await _upload(client, h, "live.txt", None)
    dead_doc = await _upload(client, h, "dead.txt", None)
    stale_doc = await _upload(client, h, "stale.txt", None)

    live = await _create_link(client, h, live_doc["id"])
    dead = await _create_link(client, h, dead_doc["id"])
    stale = await _create_link(
        client, h, stale_doc["id"], expires_at=(datetime.now(UTC) + timedelta(hours=1)).isoformat()
    )

    live_credential = (await _open(client, live["token"]))["access_token"]
    dead_credential = (await _open(client, dead["token"]))["access_token"]
    stale_credential = (await _open(client, stale["token"]))["access_token"]

    assert (
        await client.delete(f"/api/v1/share/links/{dead['id']}/record", headers=h)
    ).status_code == 204
    await _expire_link(stale["id"])

    unknown_link = create_share_access_token(
        link_id=uuid4(), root_item_id=uuid4(), permission="downloader"
    )

    failures: dict[str, Response] = {
        "garbage credential": await _refresh(client, live["token"], "not-a-credential"),
        "credential for a link that never existed": await _refresh(
            client, live["token"], unknown_link
        ),
        "credential for a deleted link": await _refresh(client, dead["token"], dead_credential),
        "credential for an expired link": await _refresh(client, stale["token"], stale_credential),
        "a signed-in user's own access token": await _refresh(client, live["token"], owner_token),
        "dead credential at a live link's URL": await _refresh(
            client, live["token"], dead_credential
        ),
    }

    for label, resp in failures.items():
        assert resp.status_code == 404, f"{label}: {resp.status_code} {resp.text}"
        assert resp.json()["error"]["code"] == "SHARE_LINK_INVALID", label

    reference = failures["garbage credential"].json()
    for label, resp in failures.items():
        assert resp.json() == reference, f"{label} is distinguishable from the others"

    # Nothing above leaks a name, so none of them says which item was involved.
    for label, resp in failures.items():
        for name in ("live.txt", "dead.txt", "stale.txt"):
            assert name not in resp.text, f"{label} leaked {name}"

    # The control: the same endpoint, one live credential, succeeds.
    ok = await _refresh(client, live["token"], live_credential)
    assert ok.status_code == 200, ok.text
    assert ok.json()["item"]["name"] == "live.txt"

    # Presenting no credential at all is 401 rather than 404. That is not an
    # enumeration signal — it reports that nothing was offered, and is reached
    # before any link is looked up — but the error code stays the same one.
    empty = await client.post(f"/api/v1/public/links/{live['token']}/session/refresh")
    assert empty.status_code == 401
    assert empty.json()["error"]["code"] == "SHARE_LINK_INVALID"


# --- renewal must not grant more than the link does --------------------------


async def test_refreshing_a_viewer_link_stays_a_viewer_link(client: AsyncClient) -> None:
    """API-PUB-11 — proposal §28.3 rule 4.

    The renewed credential is put through every ability a viewer must not have:
    downloading a file, zipping the folder and writing into it. Browsing still
    works, which is what makes the three refusals permission decisions rather
    than a rejected credential.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-viewer@test.com"))
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "ViewOnly"}, headers=h)
    ).json()
    child = await _upload(client, h, "peek.txt", folder["id"])
    link = await _create_link(client, h, folder["id"], permission="viewer")

    first = await _open(client, link["token"])
    assert first["permission"] == "viewer"
    resp = await _refresh(client, link["token"], first["access_token"])
    assert resp.status_code == 200, resp.text

    renewed = resp.json()
    assert renewed["permission"] == "viewer", "refresh must not upgrade the link"
    assert decode_share_access_token(renewed["access_token"]).permission == "viewer"
    guest = _guest(renewed["access_token"])

    listing = await client.get(f"/api/v1/public/items/{folder['id']}/children", headers=guest)
    assert listing.status_code == 200, listing.text
    assert [i["name"] for i in listing.json()["items"]] == ["peek.txt"]

    for label, refused in (
        (
            "download",
            await client.get(f"/api/v1/public/items/{child['id']}/download", headers=guest),
        ),
        ("archive", await client.get("/api/v1/public/archive", headers=guest)),
        (
            "upload",
            await client.post(
                f"/api/v1/public/items/{folder['id']}/upload",
                headers=guest,
                files={"file": ("nope.txt", io.BytesIO(b"x"), "text/plain")},
            ),
        ),
    ):
        assert refused.status_code == 403, f"{label}: {refused.status_code} {refused.text}"
        assert refused.json()["error"]["code"] == "FORBIDDEN", label


async def test_a_credential_claiming_more_than_the_link_grants_gains_nothing(
    client: AsyncClient,
) -> None:
    """proposal §28.3 rule 4, design §6.12.11b — abilities come from the row.

    Guards the invariant behind the whole credential design: what a guest may do
    is read from the link on every request, never taken from the credential.
    Minting a credential that claims `editor` for a `viewer` link needs the
    signing key and so is not a live attack; it is here because it is the only
    way to prove the claim is not what is consulted, and because a refresh
    re-issues that claim.
    """
    h = auth_headers(await register_and_login(client, email="pub-refresh-claim@test.com"))
    folder = (
        await client.post("/api/v1/drive/folders", json={"name": "StillViewOnly"}, headers=h)
    ).json()
    child = await _upload(client, h, "guarded-child.txt", folder["id"])
    link = await _create_link(client, h, folder["id"], permission="viewer")

    overclaiming = create_share_access_token(
        link_id=UUID(link["id"]),
        root_item_id=UUID(folder["id"]),
        permission="editor",
    )
    resp = await _refresh(client, link["token"], overclaiming)
    assert resp.status_code == 200, resp.text
    guest = _guest(resp.json()["access_token"])

    # Accepted as a credential...
    root = await client.get("/api/v1/public/items", headers=guest)
    assert root.status_code == 200
    assert root.json()["id"] == folder["id"]

    # ...and still held to what the link actually grants.
    download = await client.get(f"/api/v1/public/items/{child['id']}/download", headers=guest)
    assert download.status_code == 403, download.text
    written = await client.post(
        "/api/v1/public/folders",
        headers=guest,
        json={"parent_id": folder["id"], "name": "Intruder"},
    )
    assert written.status_code == 403, written.text

    # Nothing was created, checked from the owner's side rather than the refusal.
    listing = await client.get(f"/api/v1/drive/items?parent_id={folder['id']}", headers=h)
    assert [i["name"] for i in listing.json()["items"]] == ["guarded-child.txt"]
