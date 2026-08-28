"""External model connections (Settings page) — API-USER-09, proposal §12.

Covers `GET/POST/PUT/DELETE /api/v1/users/me/model-connections`. The whole point
of this feature is that a credential goes in and never comes back out, so every
test here re-reads through `GET` (never trusting the writing endpoint's own echo)
and the at-rest tests go one step further and read the row straight out of
Postgres with `_SessionFactory`, because "the API did not show me the key" is not
the same claim as "the key is not sitting in the database in plaintext".

Multi-tenant checks are A4: a second registered user drives the request, and the
owner re-reads afterwards to prove nothing moved.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.external_model.crypto import CredentialCipher
from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

_ENCRYPTION_KEY = get_settings().credential_encryption_key

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not _ENCRYPTION_KEY,
        # tests/conftest.py seeds a generated Fernet key, so this normally runs.
        # Without the key the service has no cipher and every create/update
        # answers 503 by design, which would make these assertions meaningless.
        reason="CREDENTIAL_ENCRYPTION_KEY is not configured; the feature is off",
    ),
]

_PREFIX = "/api/v1/users/me/model-connections"

# crypto.mask_secret joins the visible ends with U+2026. Written as an escape so
# no non-ASCII character ends up in this file.
_ELLIPSIS = "\u2026"

# Exactly what ConnectionView promises. Anything extra is a leak.
_VIEW_FIELDS = {
    "id",
    "label",
    "kind",
    "base_url",
    "model",
    "masked_hint",
    "status",
    "updated_at",
}


def _payload(**overrides: Any) -> dict[str, Any]:
    """A valid ConnectionCreate body, with per-test overrides."""
    body: dict[str, Any] = {
        "label": "My Gemini",
        "kind": "openai_compatible",
        "base_url": "https://models.example/v1",
        "model": "gemini-2.5-flash-lite",
        "secret": "sk-proj-integration-4321",
    }
    body.update(overrides)
    return body


async def _create(client: AsyncClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    """POST a connection and return the created view. Note the route answers 200."""
    resp = await client.post(_PREFIX, json=_payload(**overrides), headers=headers)
    assert resp.status_code == 200, resp.text
    created: dict[str, Any] = resp.json()
    return created


async def _list(client: AsyncClient, headers: dict[str, str]) -> list[dict[str, Any]]:
    resp = await client.get(_PREFIX, headers=headers)
    assert resp.status_code == 200, resp.text
    rows: list[dict[str, Any]] = resp.json()
    return rows


async def _db_row(connection_id: str) -> dict[str, Any]:
    """Read the stored row directly from Postgres, bypassing the API entirely."""
    async with _SessionFactory() as session:
        result = await session.execute(
            text(
                "SELECT user_id, label, base_url, model, secret_encrypted, "
                "masked_hint, status FROM external_model_connections WHERE id = :id"
            ),
            {"id": UUID(connection_id)},
        )
        return dict(result.mappings().one())


async def _db_count() -> int:
    async with _SessionFactory() as session:
        result = await session.execute(text("SELECT count(*) FROM external_model_connections"))
        return int(result.scalar_one())


async def _force_status(connection_id: str, status: str) -> None:
    """Set `status` at the DB level.

    Only the runtime marks a connection invalid (on ExternalAuthError during a
    real model call), so there is no endpoint that can arrange this state.
    """
    async with _SessionFactory() as session:
        await session.execute(
            text("UPDATE external_model_connections SET status = :s WHERE id = :id"),
            {"s": status, "id": UUID(connection_id)},
        )
        await session.commit()


# --- Masking and encryption at rest -----------------------------------------


async def test_created_connection_reads_back_masked_never_plaintext(client: AsyncClient) -> None:
    """API-USER-09 (masking half) — §12: only a masked hint is ever returned."""
    h = auth_headers(await register_and_login(client, email="conn-mask@test.com"))
    secret = "sk-proj-super-secret-4321"

    created = await _create(client, h, secret=secret)
    assert created["label"] == "My Gemini"
    assert created["kind"] == "openai_compatible"
    assert created["status"] == "active"

    resp = await client.get(_PREFIX, headers=h)
    assert resp.status_code == 200, resp.text
    rows: list[dict[str, Any]] = resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == created["id"]
    assert row["model"] == "gemini-2.5-flash-lite"
    assert row["base_url"] == "https://models.example/v1"
    # First 3 + last 4, per crypto.mask_secret.
    assert row["masked_hint"] == f"sk-{_ELLIPSIS}4321"
    assert set(row) == _VIEW_FIELDS, row
    assert secret not in resp.text
    assert "secret_encrypted" not in resp.text


async def test_secret_is_stored_as_fernet_ciphertext(client: AsyncClient) -> None:
    """API-USER-09 (at-rest half, A3) — §12 and §22 item 4.

    Reads `external_model_connections.secret_encrypted` out of Postgres and
    proves it is a Fernet token that round-trips back to the submitted key.
    """
    h = auth_headers(await register_and_login(client, email="conn-cipher@test.com"))
    secret = "sk-proj-at-rest-9876"

    created = await _create(client, h, secret=secret)
    row = await _db_row(created["id"])
    stored = str(row["secret_encrypted"])

    assert stored != secret
    assert secret not in stored
    assert stored.startswith("gAAAAA"), stored[:12]  # Fernet v1 token prefix
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(stored) == secret
    assert row["masked_hint"] == f"sk-{_ELLIPSIS}9876"
    assert row["status"] == "active"


async def test_short_secret_is_masked_down_to_two_characters(client: AsyncClient) -> None:
    """A secret of 8 chars or fewer must not fall back to showing itself."""
    h = auth_headers(await register_and_login(client, email="conn-short@test.com"))
    secret = "sk-12345"  # exactly 8 chars, the mask_secret boundary

    created = await _create(client, h, secret=secret)
    rows = await _list(client, h)

    assert rows[0]["masked_hint"] == f"{_ELLIPSIS}45"
    stored = str((await _db_row(created["id"]))["secret_encrypted"])
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(stored) == secret


async def test_codex_auth_json_is_encrypted_and_never_echoed(client: AsyncClient) -> None:
    """The `codex` kind stores a whole auth.json (refresh token inside), §12.

    base_url and model are optional for this kind, so this also pins their
    empty-string defaults.
    """
    h = auth_headers(await register_and_login(client, email="conn-codex@test.com"))
    auth_json = json.dumps(
        {
            "tokens": {
                "access_token": "codex-access-token-abcd",
                "refresh_token": "codex-refresh-token-wxyz",
            }
        }
    )

    resp = await client.post(
        _PREFIX,
        json={"label": "My ChatGPT", "kind": "codex", "secret": auth_json},
        headers=h,
    )
    assert resp.status_code == 200, resp.text
    created: dict[str, Any] = resp.json()
    assert created["kind"] == "codex"
    assert created["base_url"] == ""
    assert created["model"] == ""

    listed = await client.get(_PREFIX, headers=h)
    assert listed.status_code == 200, listed.text
    assert "codex-access-token-abcd" not in listed.text
    assert "codex-refresh-token-wxyz" not in listed.text
    assert set(listed.json()[0]) == _VIEW_FIELDS

    stored = str((await _db_row(created["id"]))["secret_encrypted"])
    assert "codex-access-token-abcd" not in stored
    assert "codex-refresh-token-wxyz" not in stored
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(stored) == auth_json


# --- Update -----------------------------------------------------------------


async def test_edits_are_visible_on_a_fresh_read(client: AsyncClient) -> None:
    """API-USER-09 (A2) — PUT then re-list; omitting `secret` keeps the old one."""
    h = auth_headers(await register_and_login(client, email="conn-edit@test.com"))
    created = await _create(client, h)
    before = await _db_row(created["id"])

    resp = await client.put(
        f"{_PREFIX}/{created['id']}",
        json={
            "label": "Renamed",
            "model": "gemini-3-pro",
            "base_url": "https://other.example/v1",
        },
        headers=h,
    )
    assert resp.status_code == 200, resp.text

    rows = await _list(client, h)
    assert len(rows) == 1
    assert rows[0]["label"] == "Renamed"
    assert rows[0]["model"] == "gemini-3-pro"
    assert rows[0]["base_url"] == "https://other.example/v1"
    assert rows[0]["masked_hint"] == created["masked_hint"]
    assert datetime.fromisoformat(rows[0]["updated_at"]) >= datetime.fromisoformat(
        created["updated_at"]
    )

    after = await _db_row(created["id"])
    assert after["secret_encrypted"] == before["secret_encrypted"]


async def test_rotating_the_secret_remasks_reencrypts_and_reactivates(
    client: AsyncClient,
) -> None:
    """API-USER-09 (A3) — a new secret replaces the ciphertext and clears `invalid`.

    service.update() passes `status="active"` only when a secret is supplied, so
    the connection must come back usable after a key rotation.
    """
    h = auth_headers(await register_and_login(client, email="conn-rotate@test.com"))
    created = await _create(client, h, secret="sk-old-key-1111")
    before = await _db_row(created["id"])

    await _force_status(created["id"], "invalid")
    assert (await _list(client, h))[0]["status"] == "invalid"

    new_secret = "sk-new-key-2222"
    resp = await client.put(f"{_PREFIX}/{created['id']}", json={"secret": new_secret}, headers=h)
    assert resp.status_code == 200, resp.text

    listed = await client.get(_PREFIX, headers=h)
    rows: list[dict[str, Any]] = listed.json()
    assert rows[0]["masked_hint"] == f"sk-{_ELLIPSIS}2222"
    assert rows[0]["status"] == "active"
    assert rows[0]["label"] == "My Gemini"  # untouched fields survive
    assert new_secret not in listed.text
    assert "sk-old-key-1111" not in listed.text

    after = await _db_row(created["id"])
    stored = str(after["secret_encrypted"])
    assert stored != str(before["secret_encrypted"])
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(stored) == new_secret


async def test_editing_an_unknown_connection_is_404(client: AsyncClient) -> None:
    """A random id must not be silently created or 500."""
    h = auth_headers(await register_and_login(client, email="conn-ghost@test.com"))

    resp = await client.put(f"{_PREFIX}/{uuid4()}", json={"label": "ghost"}, headers=h)

    assert resp.status_code == 404, resp.text
    # NOTE: this route raises a bare HTTPException, so the body is FastAPI's
    # {"detail": ...} rather than the §19 {"error": {code, message, details}}
    # envelope every AppError route returns.
    assert resp.json()["detail"] == "Connection not found"
    assert await _db_count() == 0


# --- Delete -----------------------------------------------------------------


async def test_deleted_connection_disappears_from_list_and_db(client: AsyncClient) -> None:
    """API-USER-09 (A3) — 204, then the row is gone from both the API and the table."""
    h = auth_headers(await register_and_login(client, email="conn-delete@test.com"))
    keep = await _create(client, h, label="Keep", secret="sk-keep-0001")
    drop = await _create(client, h, label="Drop", secret="sk-drop-0002")
    assert await _db_count() == 2

    resp = await client.delete(f"{_PREFIX}/{drop['id']}", headers=h)
    assert resp.status_code == 204, resp.text
    assert resp.content == b""

    rows = await _list(client, h)
    assert [r["id"] for r in rows] == [keep["id"]]
    assert [r["label"] for r in rows] == ["Keep"]
    assert await _db_count() == 1


async def test_connections_are_listed_in_creation_order(client: AsyncClient) -> None:
    """The repository orders by created_at asc, which is what the Settings list shows."""
    h = auth_headers(await register_and_login(client, email="conn-order@test.com"))
    first = await _create(client, h, label="First", secret="sk-aaaa-0001")
    second = await _create(client, h, label="Second", secret="sk-bbbb-0002")
    third = await _create(client, h, label="Third", secret="sk-cccc-0003")

    rows = await _list(client, h)

    assert [r["label"] for r in rows] == ["First", "Second", "Third"]
    assert [r["id"] for r in rows] == [first["id"], second["id"], third["id"]]


# --- Multi-tenant isolation (A4) --------------------------------------------


async def test_another_users_connections_are_invisible(client: AsyncClient) -> None:
    """API-USER-09 (A4) — B must not see A's connection or its mask."""
    h_a = auth_headers(await register_and_login(client, email="iso-a@test.com", username="isoa"))
    h_b = auth_headers(await register_and_login(client, email="iso-b@test.com", username="isob"))
    created = await _create(client, h_a, label="A private", secret="sk-only-mine-7777")

    resp_b = await client.get(_PREFIX, headers=h_b)
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json() == []
    assert "A private" not in resp_b.text
    assert f"sk-{_ELLIPSIS}7777" not in resp_b.text

    assert [r["id"] for r in await _list(client, h_a)] == [created["id"]]


async def test_another_user_cannot_edit_my_connection(client: AsyncClient) -> None:
    """API-USER-09 (A4) — the repo scopes update by user_id, so B gets 404."""
    h_a = auth_headers(await register_and_login(client, email="edit-a@test.com", username="edita"))
    h_b = auth_headers(await register_and_login(client, email="edit-b@test.com", username="editb"))
    created = await _create(client, h_a, secret="sk-owner-key-5555")
    before = await _db_row(created["id"])

    resp = await client.put(
        f"{_PREFIX}/{created['id']}",
        json={"label": "Hijacked", "secret": "sk-attacker-0000"},
        headers=h_b,
    )
    assert resp.status_code == 404, resp.text

    rows = await _list(client, h_a)
    assert rows[0]["label"] == "My Gemini"
    assert rows[0]["masked_hint"] == f"sk-{_ELLIPSIS}5555"
    after = await _db_row(created["id"])
    assert after["secret_encrypted"] == before["secret_encrypted"]
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(str(after["secret_encrypted"])) == (
        "sk-owner-key-5555"
    )


async def test_another_user_cannot_delete_my_connection(client: AsyncClient) -> None:
    """API-USER-09 (A4) — B's DELETE must leave A's row in place.

    NOTE: the route discards service.delete()'s boolean, so a stranger's DELETE
    answers 204 even though nothing was removed. That is not an ownership hole
    (the repository scopes by user_id), but the status code does not distinguish
    "deleted" from "not yours", unlike PUT which answers 404.
    """
    h_a = auth_headers(await register_and_login(client, email="del-a@test.com", username="dela"))
    h_b = auth_headers(await register_and_login(client, email="del-b@test.com", username="delb"))
    owner_id = (await client.get("/api/v1/users/me", headers=h_a)).json()["id"]
    created = await _create(client, h_a, secret="sk-keep-me-3333")

    resp = await client.delete(f"{_PREFIX}/{created['id']}", headers=h_b)
    assert resp.status_code == 204, resp.text

    rows = await _list(client, h_a)
    assert [r["id"] for r in rows] == [created["id"]]
    assert rows[0]["masked_hint"] == f"sk-{_ELLIPSIS}3333"
    assert await _db_count() == 1
    row = await _db_row(created["id"])
    assert str(row["user_id"]) == owner_id
    assert CredentialCipher(_ENCRYPTION_KEY).decrypt(str(row["secret_encrypted"])) == (
        "sk-keep-me-3333"
    )


# --- Input validation -------------------------------------------------------


async def test_creating_without_a_secret_is_rejected(client: AsyncClient) -> None:
    """`secret` is required; a connection with no credential must not be stored."""
    h = auth_headers(await register_and_login(client, email="val-secret@test.com"))

    resp = await client.post(
        _PREFIX,
        json={"label": "No key", "kind": "openai_compatible", "base_url": "https://x/v1"},
        headers=h,
    )

    assert resp.status_code == 422, resp.text
    assert await _list(client, h) == []
    assert await _db_count() == 0


async def test_creating_with_an_unsupported_kind_is_rejected(client: AsyncClient) -> None:
    """ConnectionKind is a Literal of three values; Anthropic is still planned (§12)."""
    h = auth_headers(await register_and_login(client, email="val-kind@test.com"))

    resp = await client.post(_PREFIX, json=_payload(kind="anthropic"), headers=h)

    assert resp.status_code == 422, resp.text
    assert await _db_count() == 0


async def test_blank_label_and_blank_secret_are_rejected(client: AsyncClient) -> None:
    """min_length=1 on both fields; empty strings must not reach the cipher."""
    h = auth_headers(await register_and_login(client, email="val-blank@test.com"))

    blank_label = await client.post(_PREFIX, json=_payload(label=""), headers=h)
    blank_secret = await client.post(_PREFIX, json=_payload(secret=""), headers=h)

    assert blank_label.status_code == 422, blank_label.text
    assert blank_secret.status_code == 422, blank_secret.text
    assert await _list(client, h) == []
    assert await _db_count() == 0


async def test_oversized_label_is_rejected(client: AsyncClient) -> None:
    """max_length=100 on label — the DB column is String(100), so this must not
    reach Postgres and blow up as a 500."""
    h = auth_headers(await register_and_login(client, email="val-long@test.com"))

    resp = await client.post(_PREFIX, json=_payload(label="L" * 101), headers=h)

    assert resp.status_code == 422, resp.text
    assert await _db_count() == 0


async def test_updating_to_a_blank_label_is_rejected(client: AsyncClient) -> None:
    """ConnectionUpdate keeps min_length=1, so a rename cannot empty the label."""
    h = auth_headers(await register_and_login(client, email="val-rename@test.com"))
    created = await _create(client, h)

    resp = await client.put(f"{_PREFIX}/{created['id']}", json={"label": ""}, headers=h)

    assert resp.status_code == 422, resp.text
    assert (await _list(client, h))[0]["label"] == "My Gemini"
