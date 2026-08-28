"""
Integration tests for Time Machine usage reporting and settings (proposal 30).

Covers doc/test-cases.md API-SU-01..05 plus the settings endpoints themselves:
GET/PUT /snapshots/settings and GET /snapshots/{id}/items.

The sharp edge here is that snapshots reference existing blobs instead of
copying them, so three different numbers describe the same snapshot and only
one of them answers "what do I get back if I delete this?":

* ``total_bytes``       -- coverage: the bytes the snapshot describes.
* ``reclaimable_bytes`` -- cost: the blobs this snapshot alone still holds.
* ``used_bytes``        -- the whole timeline, deduped by content checksum.

Regression d69851c reported coverage where cost belonged, which told users to
delete the biggest snapshot when doing so freed nothing at all. The sharing
relation is computed per ``storage_key`` (30.4 decision 3), not per checksum,
so two identical uploads cost two blobs even though they share one checksum --
that asymmetry is asserted directly in
``test_sharing_is_computed_per_storage_key_not_per_checksum``.
"""

from __future__ import annotations

import hashlib
import io
import os
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import _STORAGE_DIR, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    data: bytes,
    parent_id: str | None = None,
) -> dict[str, Any]:
    """Upload one file and return the created drive item."""
    params: dict[str, str] | None = {"parent_id": parent_id} if parent_id else None
    resp = await client.post(
        "/api/v1/upload/simple",
        headers=headers,
        params=params,
        files={"file": (name, io.BytesIO(data), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    item: dict[str, Any] = resp.json()
    return item


async def _snapshot(client: AsyncClient, headers: dict[str, str], *, label: str) -> dict[str, Any]:
    """Take a manual snapshot and return the created snapshot row."""
    resp = await client.post("/api/v1/snapshots", json={"label": label}, headers=headers)
    assert resp.status_code == 200, resp.text
    snap: dict[str, Any] = resp.json()
    return snap


async def _list_snapshots(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp = await client.get("/api/v1/snapshots", headers=headers)
    assert resp.status_code == 200, resp.text
    snaps: list[dict[str, Any]] = resp.json()
    return snaps


async def _get_settings(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = await client.get("/api/v1/snapshots/settings", headers=headers)
    assert resp.status_code == 200, resp.text
    settings: dict[str, Any] = resp.json()
    return settings


async def _put_settings(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    retention_n: int = 50,
    schedule_enabled: bool = True,
    schedule_interval_minutes: int = 60,
    quota_bytes: int | None = None,
) -> dict[str, Any]:
    resp = await client.put(
        "/api/v1/snapshots/settings",
        json={
            "retention_n": retention_n,
            "schedule_enabled": schedule_enabled,
            "schedule_interval_minutes": schedule_interval_minutes,
            "quota_bytes": quota_bytes,
        },
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    settings: dict[str, Any] = resp.json()
    return settings


async def _file_quota(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    resp = await client.get("/api/v1/users/me/quota", headers=headers)
    assert resp.status_code == 200, resp.text
    quota: dict[str, Any] = resp.json()
    return quota


async def _purge(client: AsyncClient, headers: dict[str, str], item_id: str) -> None:
    """Trash an item and then permanently delete it (metadata fully gone)."""
    trashed = await client.post(f"/api/v1/trash/items/{item_id}", headers=headers)
    assert trashed.status_code == 200, trashed.text
    gone = await client.delete(f"/api/v1/trash/items/{item_id}", headers=headers)
    assert gone.status_code == 204, gone.text


def _blob_count() -> int:
    """Number of blob files currently on the local storage backend.

    The storage dir is shared for the whole session and is not truncated between
    tests, so only the delta measured inside a single test is meaningful.
    """
    total = 0
    for _root, _dirs, files in os.walk(_STORAGE_DIR):
        total += len(files)
    return total


def _by_label(snaps: list[dict[str, Any]], label: str) -> dict[str, Any]:
    match = next((s for s in snaps if s["label"] == label), None)
    assert match is not None, f"snapshot {label!r} missing from {[s['label'] for s in snaps]}"
    return match


async def _seed_keeper_and_purged_file(
    client: AsyncClient, headers: dict[str, str]
) -> dict[str, str]:
    """Build the coverage-vs-cost fixture used by API-SU-02/03/04.

    Snapshot "only-keeper" covers a file that is still live (so it holds nothing
    exclusively). Snapshot "keeper-and-doomed" additionally covers a file that
    has since been permanently deleted, making it the sole remaining holder of
    that blob. Returns the two drive item ids.
    """
    keeper = await _upload(client, headers, name="keeper.txt", data=b"k" * 3000)
    await _snapshot(client, headers, label="only-keeper")
    doomed = await _upload(client, headers, name="doomed.txt", data=b"d" * 7000)
    await _snapshot(client, headers, label="keeper-and-doomed")
    await _purge(client, headers, str(doomed["id"]))
    return {"keeper_id": str(keeper["id"]), "doomed_id": str(doomed["id"])}


# ---------------------------------------------------------------------------
# API-SU-01 -- settings expose usage and the effective cap
# ---------------------------------------------------------------------------


async def test_settings_expose_usage_and_effective_quota_for_a_fresh_user(
    client: AsyncClient,
) -> None:
    """API-SU-01 (proposal 30.4-4): defaults, used_bytes and effective_quota_bytes.

    A user who never touched Time Machine still gets a complete settings payload:
    quota_bytes is null (auto) while effective_quota_bytes resolves to half the
    file quota, so the UI always has a number to draw a gauge against.
    """
    token = await register_and_login(client, email="su-defaults@test.com", username="sudef")
    h = auth_headers(token)

    settings = await _get_settings(client, h)

    assert settings["retention_n"] == 50
    assert settings["schedule_enabled"] is True
    assert settings["schedule_interval_minutes"] == 60
    assert settings["quota_bytes"] is None  # auto
    assert settings["used_bytes"] == 0

    quota = await _file_quota(client, h)
    assert settings["effective_quota_bytes"] == quota["quota_bytes"] // 2
    assert settings["effective_quota_bytes"] > 0


async def test_snapshot_usage_is_accounted_separately_from_the_file_quota(
    client: AsyncClient,
) -> None:
    """API-SU-01 (A3): taking a snapshot consumes snapshot quota, not file quota.

    A snapshot copies no blobs, so the file quota must not move and no new blob
    may appear on disk -- only the snapshot-side used_bytes grows.
    """
    token = await register_and_login(client, email="su-separate@test.com", username="susep")
    h = auth_headers(token)

    await _upload(client, h, name="doc.txt", data=b"q" * 4096)

    quota_before = await _file_quota(client, h)
    settings_before = await _get_settings(client, h)
    assert quota_before["used_bytes"] == 4096  # the upload counts against files
    assert settings_before["used_bytes"] == 0  # nothing captured yet

    blobs_before = _blob_count()
    snap = await _snapshot(client, h, label="after upload")
    blobs_after = _blob_count()

    quota_after = await _file_quota(client, h)
    settings_after = await _get_settings(client, h)

    assert blobs_after == blobs_before, "a snapshot must not duplicate any blob"
    assert quota_after["used_bytes"] == 4096, "snapshotting must not charge the file quota"
    assert quota_after["quota_bytes"] == quota_before["quota_bytes"]
    assert settings_after["used_bytes"] == 4096, "the snapshot side must account for it"
    assert settings_after["effective_quota_bytes"] == quota_after["quota_bytes"] // 2
    assert settings_after["used_bytes"] < settings_after["effective_quota_bytes"]

    listed = await _list_snapshots(client, h)
    assert [s["id"] for s in listed] == [snap["id"]]
    assert listed[0]["total_bytes"] == 4096


async def test_used_bytes_counts_content_shared_by_two_snapshots_only_once(
    client: AsyncClient,
) -> None:
    """API-SU-01 (A3): timeline usage is deduped, not the sum of coverage.

    Two snapshots of the same unchanged file each cover 6000 bytes, but the
    timeline occupies 6000 bytes in total -- one blob.
    """
    token = await register_and_login(client, email="su-dedupe@test.com", username="sudedupe")
    h = auth_headers(token)

    await _upload(client, h, name="stable.txt", data=b"s" * 6000)
    await _snapshot(client, h, label="first")
    await _snapshot(client, h, label="second")

    snaps = await _list_snapshots(client, h)
    assert len(snaps) == 2
    assert sum(s["total_bytes"] for s in snaps) == 12000  # coverage counts it twice

    settings = await _get_settings(client, h)
    assert settings["used_bytes"] == 6000  # storage counts it once


# ---------------------------------------------------------------------------
# API-SU-02/03/04 -- reclaimable is cost, not coverage
# ---------------------------------------------------------------------------


async def test_reclaimable_bytes_is_what_deleting_frees_not_what_it_covers(
    client: AsyncClient,
) -> None:
    """API-SU-02 (A3, regression d69851c): coverage is not cost.

    "keeper-and-doomed" covers 10000 bytes but only the 7000-byte purged file is
    exclusively its own; the 3000-byte keeper is still referenced by the live
    drive item and by the older snapshot. Reporting total_bytes here would have
    promised 10000 bytes that deleting cannot deliver.
    """
    token = await register_and_login(client, email="su-cost@test.com", username="sucost")
    h = auth_headers(token)
    ids = await _seed_keeper_and_purged_file(client, h)

    snaps = await _list_snapshots(client, h)
    older = _by_label(snaps, "only-keeper")
    newer = _by_label(snaps, "keeper-and-doomed")

    assert older["total_bytes"] == 3000
    assert newer["total_bytes"] == 10000

    assert newer["reclaimable_bytes"] == 7000, "only the purged file's blob is exclusive"
    assert older["reclaimable_bytes"] == 0, "its only blob is still held elsewhere"

    # The keeper is genuinely still there -- the zero above is a real shared
    # reference, not an accounting shortcut.
    got = await client.get(f"/api/v1/download/{ids['keeper_id']}", headers=h)
    assert got.status_code == 200
    assert got.content == b"k" * 3000


async def test_purging_a_file_keeps_the_blob_a_snapshot_still_needs(client: AsyncClient) -> None:
    """API-SU-02 (A3, blob level): the reclaimable bytes really are still on disk.

    Permanent delete removes the metadata but must leave a blob that Time
    Machine still references, otherwise the snapshot's reported reclaimable
    bytes would be describing something already gone.
    """
    token = await register_and_login(client, email="su-blob@test.com", username="sublob")
    h = auth_headers(token)

    doomed = await _upload(client, h, name="doomed.txt", data=b"d" * 7000)
    await _snapshot(client, h, label="before purge")

    blobs_before = _blob_count()
    await _purge(client, h, str(doomed["id"]))
    blobs_after = _blob_count()

    assert blobs_after == blobs_before, "the snapshot still references this blob"

    # The drive no longer knows about the file...
    listing = await client.get("/api/v1/drive/items", headers=h)
    assert "doomed.txt" not in [i["name"] for i in listing.json()["items"]]
    dead = await client.get(f"/api/v1/download/{doomed['id']}", headers=h)
    assert dead.status_code == 404

    # ...but the snapshot still lists it, and now owns it exclusively.
    snaps = await _list_snapshots(client, h)
    entries = await client.get(f"/api/v1/snapshots/{snaps[0]['id']}/items", headers=h)
    assert [e["name"] for e in entries.json()] == ["doomed.txt"]
    assert snaps[0]["reclaimable_bytes"] == 7000


async def test_snapshots_with_zero_reclaimable_bytes_are_still_listed(
    client: AsyncClient,
) -> None:
    """API-SU-03: a snapshot that frees nothing must not be filtered out.

    The reclaimable query only returns rows for exclusively-held blobs, so a
    snapshot that shares everything produces no row at all -- it has to be
    filled in as 0 rather than dropped from the timeline.
    """
    token = await register_and_login(client, email="su-zero@test.com", username="suzero")
    h = auth_headers(token)
    await _seed_keeper_and_purged_file(client, h)

    snaps = await _list_snapshots(client, h)
    labels = sorted(s["label"] for s in snaps)
    assert labels == ["keeper-and-doomed", "only-keeper"]

    zero = _by_label(snaps, "only-keeper")
    assert zero["reclaimable_bytes"] == 0
    assert zero["total_bytes"] == 3000  # it still covers content
    assert zero["item_count"] == 1


async def test_every_snapshot_row_reports_both_coverage_and_reclaimable(
    client: AsyncClient,
) -> None:
    """API-SU-04: both numbers appear on every row, not one or the other."""
    token = await register_and_login(client, email="su-both@test.com", username="suboth")
    h = auth_headers(token)
    await _seed_keeper_and_purged_file(client, h)

    snaps = await _list_snapshots(client, h)
    assert len(snaps) == 2
    # Assert the actual numbers, not their types: the response schema already
    # guarantees both keys exist and are ints, so a shape check here could
    # never fail and would prove nothing about the accounting.
    by_label = {s["label"]: (s["total_bytes"], s["reclaimable_bytes"]) for s in snaps}
    assert by_label == {"only-keeper": (3000, 0), "keeper-and-doomed": (10000, 7000)}
    assert [s["trigger"] for s in snaps] == ["manual", "manual"]
    assert [s["pinned"] for s in snaps] == [False, False]


# ---------------------------------------------------------------------------
# API-SU-05 -- sharing is per storage_key, not per checksum
# ---------------------------------------------------------------------------


async def test_sharing_is_computed_per_storage_key_not_per_checksum(
    client: AsyncClient,
) -> None:
    """API-SU-05 (A3, proposal 30.4 decision 3): two identical uploads cost two blobs.

    Uploads are not content-addressed: each gets its own storage_key, so byte
    identical twins share a checksum but occupy two blobs. Deleting the snapshot
    therefore frees 8192 bytes even though the timeline's checksum-deduped
    used_bytes is only 4096. A checksum-based sharing relation would have
    reported 4096 and under-promised by half.
    """
    token = await register_and_login(client, email="su-key@test.com", username="sukey")
    h = auth_headers(token)

    payload = b"z" * 4096
    twin_a = await _upload(client, h, name="twin_a.txt", data=payload)
    twin_b = await _upload(client, h, name="twin_b.txt", data=payload)
    snap = await _snapshot(client, h, label="twins")

    entries = await client.get(f"/api/v1/snapshots/{snap['id']}/items", headers=h)
    assert entries.status_code == 200, entries.text
    rows = entries.json()
    assert [r["name"] for r in rows] == ["twin_a.txt", "twin_b.txt"]
    # One checksum, two entries -- the premise of this test.
    assert {r["checksum_sha256"] for r in rows} == {hashlib.sha256(payload).hexdigest()}

    listed = await _list_snapshots(client, h)
    assert listed[0]["total_bytes"] == 8192  # coverage sums both files
    settings = await _get_settings(client, h)
    assert settings["used_bytes"] == 4096  # usage dedupes by checksum

    # Drop both live items so the snapshot becomes the sole holder of both keys.
    await _purge(client, h, str(twin_a["id"]))
    await _purge(client, h, str(twin_b["id"]))

    after = await _list_snapshots(client, h)
    assert len(after) == 1
    # 8192, not 4096: the two uploads are byte-identical (same checksum) but land
    # on two storage_keys, and it is keys that occupy the disk (§30.4 decision 3).
    assert after[0]["reclaimable_bytes"] == 8192, "two distinct storage_keys are freed"

    still = await _get_settings(client, h)
    assert still["used_bytes"] == 4096, "checksum dedupe is unchanged by the purge"


# ---------------------------------------------------------------------------
# PUT /snapshots/settings
# ---------------------------------------------------------------------------


async def test_updated_settings_are_returned_by_a_subsequent_get(client: AsyncClient) -> None:
    """A2: retention / schedule / quota changes survive into a fresh GET.

    An explicit quota_bytes also overrides the auto half-of-file-quota rule
    without touching the file quota itself.
    """
    token = await register_and_login(client, email="su-put@test.com", username="suput")
    h = auth_headers(token)

    quota_before = await _file_quota(client, h)
    written = await _put_settings(
        client,
        h,
        retention_n=7,
        schedule_enabled=False,
        schedule_interval_minutes=15,
        quota_bytes=1_048_576,
    )
    assert written["retention_n"] == 7
    assert written["effective_quota_bytes"] == 1_048_576

    reread = await _get_settings(client, h)
    assert reread["retention_n"] == 7
    assert reread["schedule_enabled"] is False
    assert reread["schedule_interval_minutes"] == 15
    assert reread["quota_bytes"] == 1_048_576
    assert reread["effective_quota_bytes"] == 1_048_576, "explicit quota beats the auto rule"
    assert reread["used_bytes"] == 0

    quota_after = await _file_quota(client, h)
    assert quota_after["quota_bytes"] == quota_before["quota_bytes"], "file quota untouched"


async def test_clearing_the_quota_returns_to_the_auto_half_of_file_quota(
    client: AsyncClient,
) -> None:
    """A2: quota_bytes=null goes back to auto (half the file quota)."""
    token = await register_and_login(client, email="su-auto@test.com", username="suauto")
    h = auth_headers(token)

    await _put_settings(client, h, retention_n=9, quota_bytes=2048)
    pinned = await _get_settings(client, h)
    assert pinned["quota_bytes"] == 2048
    assert pinned["effective_quota_bytes"] == 2048

    await _put_settings(
        client, h, retention_n=5, schedule_enabled=True, schedule_interval_minutes=30
    )

    reread = await _get_settings(client, h)
    quota = await _file_quota(client, h)
    assert reread["quota_bytes"] is None
    assert reread["effective_quota_bytes"] == quota["quota_bytes"] // 2
    assert reread["retention_n"] == 5
    assert reread["schedule_interval_minutes"] == 30


async def test_tightening_retention_prunes_older_snapshots_immediately(
    client: AsyncClient,
) -> None:
    """A2: a retention change applies at once, not at the next capture.

    Only the newest snapshot survives retention_n=1, and the timeline read back
    afterwards proves the prune actually ran inside the PUT.
    """
    token = await register_and_login(client, email="su-prune@test.com", username="suprune")
    h = auth_headers(token)

    await _upload(client, h, name="content.txt", data=b"c" * 512)
    for label in ("first", "second", "third"):
        await _snapshot(client, h, label=label)
    assert len(await _list_snapshots(client, h)) == 3

    written = await _put_settings(client, h, retention_n=1)
    assert written["retention_n"] == 1

    survivors = await _list_snapshots(client, h)
    assert [s["label"] for s in survivors] == ["third"], "newest is always kept"

    reread = await _get_settings(client, h)
    assert reread["retention_n"] == 1


async def test_out_of_range_settings_are_rejected_and_leave_the_stored_values(
    client: AsyncClient,
) -> None:
    """A2: FastAPI request validation rejects bad payloads; nothing is written.

    Rejections use FastAPI's own 422 envelope ({"detail": [...]}), not the app's
    {"error": {...}} shape -- see InvalidOperationError's docstring on why the
    two statuses are kept apart.
    """
    token = await register_and_login(client, email="su-invalid@test.com", username="suinv")
    h = auth_headers(token)

    bad_payloads: list[dict[str, Any]] = [
        {"retention_n": 0, "schedule_enabled": True, "schedule_interval_minutes": 60},
        {"retention_n": 5, "schedule_enabled": True, "schedule_interval_minutes": 0},
        {
            "retention_n": 5,
            "schedule_enabled": True,
            "schedule_interval_minutes": 60,
            "quota_bytes": -1,
        },
        {"schedule_enabled": True, "schedule_interval_minutes": 60},  # retention_n required
    ]
    for payload in bad_payloads:
        resp = await client.put("/api/v1/snapshots/settings", json=payload, headers=h)
        assert resp.status_code == 422, f"{payload} -> {resp.status_code} {resp.text}"
        assert "detail" in resp.json()

    unchanged = await _get_settings(client, h)
    assert unchanged["retention_n"] == 50
    assert unchanged["schedule_interval_minutes"] == 60
    assert unchanged["quota_bytes"] is None


# ---------------------------------------------------------------------------
# GET /snapshots/{id}/items
# ---------------------------------------------------------------------------


async def test_snapshot_items_browse_one_folder_level_and_stay_frozen(
    client: AsyncClient,
) -> None:
    """A2: browsing a snapshot returns that folder level as it was captured.

    Renaming the live item afterwards must not leak into the snapshot view --
    the whole point of a point-in-time capture.
    """
    token = await register_and_login(client, email="su-items@test.com", username="suitems")
    h = auth_headers(token)

    folder = await client.post("/api/v1/drive/folders", json={"name": "Reports"}, headers=h)
    assert folder.status_code == 201, folder.text
    folder_id = str(folder.json()["id"])

    inner_bytes = b"inner-bytes"
    root_bytes = b"root-bytes"
    inner = await _upload(client, h, name="inner.txt", data=inner_bytes, parent_id=folder_id)
    root_file = await _upload(client, h, name="root.txt", data=root_bytes)
    snap = await _snapshot(client, h, label="tree")

    top = await client.get(f"/api/v1/snapshots/{snap['id']}/items", headers=h)
    assert top.status_code == 200, top.text
    top_rows = top.json()
    assert [r["name"] for r in top_rows] == ["Reports", "root.txt"], "ordered by name"

    folder_row = top_rows[0]
    assert folder_row["item_type"] == "FOLDER"
    assert folder_row["size_bytes"] == 0
    assert folder_row["checksum_sha256"] is None
    assert folder_row["parent_item_id"] is None
    assert folder_row["item_id"] == folder_id

    file_row = top_rows[1]
    assert file_row["item_type"] == "FILE"
    assert file_row["item_id"] == root_file["id"]
    assert file_row["size_bytes"] == len(root_bytes)
    assert file_row["checksum_sha256"] == hashlib.sha256(root_bytes).hexdigest()

    nested = await client.get(
        f"/api/v1/snapshots/{snap['id']}/items", params={"parent_id": folder_id}, headers=h
    )
    assert nested.status_code == 200, nested.text
    nested_rows = nested.json()
    assert [r["name"] for r in nested_rows] == ["inner.txt"]
    assert nested_rows[0]["item_id"] == inner["id"]
    assert nested_rows[0]["parent_item_id"] == folder_id
    assert nested_rows[0]["checksum_sha256"] == hashlib.sha256(inner_bytes).hexdigest()

    # Rename the live file; the snapshot must keep the captured name.
    renamed = await client.patch(
        f"/api/v1/drive/items/{root_file['id']}/name", json={"name": "renamed.txt"}, headers=h
    )
    assert renamed.status_code == 200, renamed.text

    again = await client.get(f"/api/v1/snapshots/{snap['id']}/items", headers=h)
    assert [r["name"] for r in again.json()] == ["Reports", "root.txt"]
    live = await client.get("/api/v1/drive/items", headers=h)
    assert "renamed.txt" in [i["name"] for i in live.json()["items"]]


async def test_browsing_an_unknown_or_foreign_snapshot_is_a_404(client: AsyncClient) -> None:
    """A4: snapshot contents are scoped to their owner; misses answer NOT_FOUND."""
    alice = await register_and_login(client, email="su-alice@test.com", username="sualice")
    bob = await register_and_login(client, email="su-bob@test.com", username="subob")
    ha, hb = auth_headers(alice), auth_headers(bob)

    await _upload(client, ha, name="private.txt", data=b"private")
    snap = await _snapshot(client, ha, label="alice only")

    missing = await client.get(f"/api/v1/snapshots/{uuid4()}/items", headers=ha)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    stolen = await client.get(f"/api/v1/snapshots/{snap['id']}/items", headers=hb)
    assert stolen.status_code == 404, "another user's snapshot must not be browsable"
    assert stolen.json()["error"]["code"] == "NOT_FOUND"

    assert await _list_snapshots(client, hb) == [], "bob's timeline stays empty"
    owner_view = await client.get(f"/api/v1/snapshots/{snap['id']}/items", headers=ha)
    assert [r["name"] for r in owner_view.json()] == ["private.txt"]


async def test_snapshot_settings_and_usage_are_per_user(client: AsyncClient) -> None:
    """A4: one user's settings and usage never bleed into another's.

    Both users share the snapshot tables, so the isolation has to come from the
    queries rather than from the data happening to be empty.
    """
    alice = await register_and_login(client, email="su-t1@test.com", username="sut1")
    bob = await register_and_login(client, email="su-t2@test.com", username="sut2")
    ha, hb = auth_headers(alice), auth_headers(bob)

    await _put_settings(
        client,
        ha,
        retention_n=3,
        schedule_enabled=False,
        schedule_interval_minutes=5,
        quota_bytes=4096,
    )

    # Bob still sees untouched defaults.
    bob_settings = await _get_settings(client, hb)
    assert bob_settings["retention_n"] == 50
    assert bob_settings["schedule_enabled"] is True
    assert bob_settings["schedule_interval_minutes"] == 60
    assert bob_settings["quota_bytes"] is None
    assert bob_settings["used_bytes"] == 0

    # Bob's own captures count only against Bob.
    await _upload(client, hb, name="bob.txt", data=b"b" * 2048)
    await _snapshot(client, hb, label="bob capture")
    assert (await _get_settings(client, hb))["used_bytes"] == 2048

    alice_settings = await _get_settings(client, ha)
    assert alice_settings["used_bytes"] == 0, "bob's bytes must not appear here"
    assert alice_settings["retention_n"] == 3
    assert alice_settings["quota_bytes"] == 4096
    assert alice_settings["effective_quota_bytes"] == 4096
    assert await _list_snapshots(client, ha) == []
