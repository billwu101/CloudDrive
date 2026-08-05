"""Share permission matrix — API-SHR-03~09, proposal §14.

§14.1 defines four levels and §14.3 item 1 says every file operation checks
them. The existing share suite proves the happy path for one level at a time;
this one runs the whole grid, because the failure mode that actually shipped
(1c1a63e) was a check that compared `owner_id` instead of asking
PermissionService — every single-level test still passed while `editor` was
silently powerless.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


@dataclass
class Shared:
    owner: dict[str, str]
    guest: dict[str, str]
    folder_id: str
    file_id: str


async def _share_a_folder(client: AsyncClient, permission: str, slug: str) -> Shared:
    """Owner creates a folder with a file inside, shared to guest at `permission`."""
    owner = auth_headers(await register_and_login(client, email=f"own-{slug}@test.com"))
    guest_email = f"guest-{slug}@test.com"
    guest = auth_headers(await register_and_login(client, email=guest_email, username=f"g{slug}"))

    folder = await client.post("/api/v1/drive/folders", json={"name": f"F-{slug}"}, headers=owner)
    folder_id = folder.json()["id"]

    upload = await client.post(
        f"/api/v1/upload/simple?parent_id={folder_id}",
        headers=owner,
        files={"file": ("inside.txt", io.BytesIO(b"contents"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text

    share = await client.post(
        f"/api/v1/share/items/{folder_id}",
        json={"target_email": guest_email, "permission": permission},
        headers=owner,
    )
    assert share.status_code in (200, 201), share.text

    return Shared(owner, guest, folder_id, upload.json()["id"])


async def test_viewer_can_look_but_not_download_or_change(client: AsyncClient) -> None:
    """API-SHR-03/04 — §14.1: viewer is 可檢視與預覽, nothing more."""
    s = await _share_a_folder(client, "viewer", "viewer")

    assert (
        await client.get(f"/api/v1/drive/items/{s.file_id}", headers=s.guest)
    ).status_code == 200
    assert (await client.get(f"/api/v1/preview/{s.file_id}", headers=s.guest)).status_code == 200

    download = await client.get(f"/api/v1/download/{s.file_id}", headers=s.guest)
    assert download.status_code == 403, download.text

    rename = await client.patch(
        f"/api/v1/drive/items/{s.file_id}/name", json={"name": "hijacked.txt"}, headers=s.guest
    )
    assert rename.status_code == 403, rename.text

    # The name really is unchanged, not merely reported as refused.
    still = await client.get(f"/api/v1/drive/items/{s.file_id}", headers=s.owner)
    assert still.json()["name"] == "inside.txt"


async def test_downloader_may_download_but_still_not_edit(client: AsyncClient) -> None:
    """API-SHR-05 — the level that exists purely to separate reading from writing."""
    s = await _share_a_folder(client, "downloader", "dl")

    download = await client.get(f"/api/v1/download/{s.file_id}", headers=s.guest)
    assert download.status_code == 200, download.text
    assert download.content == b"contents"

    rename = await client.patch(
        f"/api/v1/drive/items/{s.file_id}/name", json={"name": "nope.txt"}, headers=s.guest
    )
    assert rename.status_code == 403, rename.text


async def test_editor_can_actually_edit(client: AsyncClient) -> None:
    """API-SHR-06 — regression for 1c1a63e.

    Every assertion reads the result back through the *owner's* session, so a
    permission check that quietly no-ops cannot pass by echoing the request.
    """
    s = await _share_a_folder(client, "editor", "ed")

    rename = await client.patch(
        f"/api/v1/drive/items/{s.file_id}/name", json={"name": "edited.txt"}, headers=s.guest
    )
    assert rename.status_code == 200, rename.text

    upload = await client.post(
        f"/api/v1/upload/simple?parent_id={s.folder_id}",
        headers=s.guest,
        files={"file": ("added-by-editor.txt", io.BytesIO(b"new"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text

    seen_by_owner = await client.get(
        f"/api/v1/drive/items?parent_id={s.folder_id}", headers=s.owner
    )
    names = [i["name"] for i in seen_by_owner.json()["items"]]
    assert "edited.txt" in names, "the rename did not reach the owner's view"


async def test_an_editors_upload_is_owned_by_the_editor_not_the_folder_owner(
    client: AsyncClient,
) -> None:
    """API-SHR-06 — pins a **known gap**, deliberately, so it cannot drift silently.

    `UploadService` stamps `owner_id` with the uploader, and
    `list_children` filters on `owner_id == current user`. Together that means a
    file an editor adds to a shared folder is visible to the editor and
    **invisible in the folder owner's own listing** — the owner has to open the
    item by id to see it at all.

    This test asserts what the code does today rather than what one might expect,
    because changing it is a product decision (who owns a collaborator's upload,
    and whose quota it charges) and not something a test should force. Note the
    public-link editor path took the opposite decision in proposal §33.3 item 6,
    where anonymous uploads are charged to the item's owner.
    """
    s = await _share_a_folder(client, "editor", "edown")

    upload = await client.post(
        f"/api/v1/upload/simple?parent_id={s.folder_id}",
        headers=s.guest,
        files={"file": ("added-by-editor.txt", io.BytesIO(b"new"), "text/plain")},
    )
    assert upload.status_code == 201, upload.text
    new_id = upload.json()["id"]

    owner_view = await client.get(f"/api/v1/drive/items?parent_id={s.folder_id}", headers=s.owner)
    assert "added-by-editor.txt" not in [i["name"] for i in owner_view.json()["items"]]

    editor_view = await client.get(f"/api/v1/drive/items?parent_id={s.folder_id}", headers=s.guest)
    assert "added-by-editor.txt" in [i["name"] for i in editor_view.json()["items"]]

    # It is a real item in the owner's folder, just filtered out of their listing.
    direct = await client.get(f"/api/v1/drive/items/{new_id}", headers=s.guest)
    assert direct.status_code == 200
    assert direct.json()["parent_id"] == s.folder_id


async def test_editor_cannot_trash_or_permanently_delete(client: AsyncClient) -> None:
    """API-SHR-07 — §14.1 grants editor rename / move / upload-new-version and nothing else.

    Deletion of any kind stays with the owner, so the destructive verbs are
    refused before they reach the trash service.
    """
    s = await _share_a_folder(client, "editor", "eddel")

    trashed = await client.post(f"/api/v1/trash/items/{s.file_id}", headers=s.guest)
    assert trashed.status_code == 403, trashed.text

    purge = await client.delete(f"/api/v1/trash/items/{s.file_id}", headers=s.guest)
    assert purge.status_code in (403, 404), purge.text

    # Nothing was destroyed: the owner's file is untouched and still downloadable.
    intact = await client.get(f"/api/v1/download/{s.file_id}", headers=s.owner)
    assert intact.status_code == 200
    assert intact.content == b"contents"

    # And the owner can trash it themselves.
    by_owner = await client.post(f"/api/v1/trash/items/{s.file_id}", headers=s.owner)
    assert by_owner.status_code in (200, 204), by_owner.text


async def test_folder_permission_reaches_the_children(client: AsyncClient) -> None:
    """API-SHR-08 — §14.2 item 4.

    The share is recorded against the folder only; the file inside has no share
    row of its own, so serving it proves inheritance rather than a lucky lookup.
    """
    s = await _share_a_folder(client, "downloader", "inherit")

    nested = await client.post(
        "/api/v1/drive/folders",
        json={"name": "Deeper", "parent_id": s.folder_id},
        headers=s.owner,
    )
    deep_upload = await client.post(
        f"/api/v1/upload/simple?parent_id={nested.json()['id']}",
        headers=s.owner,
        files={"file": ("deep.txt", io.BytesIO(b"deep contents"), "text/plain")},
    )
    deep_id = deep_upload.json()["id"]

    deep = await client.get(f"/api/v1/download/{deep_id}", headers=s.guest)
    assert deep.status_code == 200, deep.text
    assert deep.content == b"deep contents"


async def test_inheritance_does_not_spill_outside_the_shared_folder(
    client: AsyncClient,
) -> None:
    """API-SHR-09 — §28.3 item 4 in spirit: a share authorises a subtree, not an account."""
    s = await _share_a_folder(client, "editor", "bound")

    outside = await client.post(
        "/api/v1/upload/simple",
        headers=s.owner,
        files={"file": ("private.txt", io.BytesIO(b"not yours"), "text/plain")},
    )
    outside_id = outside.json()["id"]

    for method, path, body in (
        ("GET", f"/api/v1/drive/items/{outside_id}", None),
        ("GET", f"/api/v1/download/{outside_id}", None),
        ("PATCH", f"/api/v1/drive/items/{outside_id}/name", {"name": "taken.txt"}),
    ):
        resp = await client.request(method, path, json=body, headers=s.guest)
        assert resp.status_code in (403, 404), f"{method} {path} → {resp.status_code}"


async def test_revoking_a_share_takes_effect_immediately(client: AsyncClient) -> None:
    """API-SHR-02 — the recipient must lose access without needing to log out."""
    s = await _share_a_folder(client, "downloader", "revoke")

    guest_me = await client.get("/api/v1/users/me", headers=s.guest)
    guest_id = guest_me.json()["id"]

    assert (await client.get(f"/api/v1/download/{s.file_id}", headers=s.guest)).status_code == 200

    removed = await client.delete(
        f"/api/v1/share/items/{s.folder_id}/users/{guest_id}", headers=s.owner
    )
    assert removed.status_code in (200, 204), removed.text

    after = await client.get(f"/api/v1/download/{s.file_id}", headers=s.guest)
    assert after.status_code in (403, 404), after.text


async def test_a_recipient_cannot_reshare_what_was_shared_with_them(
    client: AsyncClient,
) -> None:
    """API-SHR-07 — re-sharing is an owner power; §14.1 grants it to nobody else."""
    s = await _share_a_folder(client, "editor", "reshare")
    third_email = "third-party@test.com"
    await register_and_login(client, email=third_email, username="third")

    resp = await client.post(
        f"/api/v1/share/items/{s.folder_id}",
        json={"target_email": third_email, "permission": "viewer"},
        headers=s.guest,
    )
    assert resp.status_code in (403, 404), resp.text
