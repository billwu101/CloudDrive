"""Integration tests for assistant skill management (proposal 17.5).

Covers the skill lifecycle endpoints that had zero integration coverage:
``GET /assistant/skills``, ``GET /assistant/models``,
``PATCH /assistant/skills/{id}``, ``DELETE /assistant/skills/{id}``,
``POST /assistant/skills/{id}/approve`` and ``POST /assistant/skills/{id}/execute``.

Case coverage: API-AI-11 (codeguard rejects dangerous code) and API-AI-12
(an unapproved skill must not execute, and must leave no side effects).

Authoring a *generated* skill needs a reachable LLM, so the code under test is
seeded straight into Postgres instead (the repository is the only writer of a
pending proposal outside codegen). The one authoring path that needs no model at
all -- the hardcoded ``inspect_item_details`` context-menu proposal, which
``WorkflowService.chat`` short-circuits to before any model call -- is driven
through ``POST /assistant/chat`` and skips if the assistant feature flag is off.

Skill execution runs the real subprocess sandbox; no network or model involved.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient

from app.models.assistant_skill import AssistantSkill
from tests.integration.conftest import _SessionFactory, auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

SKILLS = "/api/v1/assistant/skills"
MODELS = "/api/v1/assistant/models"
CHAT = "/api/v1/assistant/chat"
DRIVE_ITEMS = "/api/v1/drive/items"
DRIVE_FOLDERS = "/api/v1/drive/folders"
UPLOAD_SIMPLE = "/api/v1/upload/simple"
SNAPSHOTS = "/api/v1/snapshots"
CONNECTIONS = "/api/v1/users/me/model-connections"

# A valid generated skill: reads the input file, writes ONE file into output_dir.
# Passes codeguard (module-level run(input_path, output_dir, params), no
# forbidden import/name/dunder) and the sandbox audit hook (only writes below
# output_dir).
UPPERCASE_CODE = '''\
from pathlib import Path


def run(input_path, output_dir, params):
    """Write an uppercased copy of the input into the output directory."""
    data = Path(input_path).read_bytes()
    target = Path(output_dir) / "upper.txt"
    target.write_bytes(data.upper())
    return {"written": target.name, "bytes": len(data)}
'''

REVERSE_CODE = '''\
from pathlib import Path


def run(input_path, output_dir, params):
    """Write a byte-reversed copy of the input into the output directory."""
    data = Path(input_path).read_bytes()
    target = Path(output_dir) / "reversed.txt"
    target.write_bytes(data[::-1])
    return {"written": target.name}
'''


def _manifest(
    name: str,
    description: str,
    item_types: list[str] | None = None,
) -> dict[str, Any]:
    """A manifest shaped exactly as ``validate_manifest`` requires.

    The context-menu handler must equal the skill name, and ``item_types``
    decides what the skill may be executed on (DEC-035).
    """
    return {
        "name": name,
        "description": description,
        "version": "1.0.0",
        "ui": {
            "context_menu": [
                {
                    "label": description,
                    "handler": name,
                    "item_types": item_types or ["FILE"],
                }
            ]
        },
    }


async def _seed_skill(
    *,
    user_id: UUID,
    name: str,
    description: str = "Uppercase a file",
    code: str = UPPERCASE_CODE,
    status: str = "installed",
    item_types: list[str] | None = None,
    chat_enabled: bool = False,
    manifest: dict[str, Any] | None = None,
) -> UUID:
    """Insert a skill row directly and return its id.

    Generated skills are only ever created by the codegen sub-agent, which needs
    a live model; seeding keeps these tests deterministic and model-free while
    every assertion still goes through the real HTTP endpoints.
    """
    now = datetime.now(UTC)
    skill_id = uuid4()
    async with _SessionFactory() as session:
        session.add(
            AssistantSkill(
                id=skill_id,
                user_id=user_id,
                name=name,
                description=description,
                manifest=manifest or _manifest(name, description, item_types),
                code=code,
                status=status,
                chat_enabled=chat_enabled,
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()
    return skill_id


async def _current_user_id(client: AsyncClient, headers: dict[str, str]) -> UUID:
    resp = await client.get("/api/v1/users/me", headers=headers)
    assert resp.status_code == 200, resp.text
    return UUID(str(resp.json()["id"]))


async def _list_items(
    client: AsyncClient,
    headers: dict[str, str],
    parent_id: str | None = None,
) -> list[dict[str, Any]]:
    params = {} if parent_id is None else {"parent_id": parent_id}
    resp = await client.get(DRIVE_ITEMS, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    items: list[dict[str, Any]] = resp.json()["items"]
    return items


async def _list_skills(
    client: AsyncClient,
    headers: dict[str, str],
    status: str | None = None,
) -> list[dict[str, Any]]:
    params = {} if status is None else {"status": status}
    resp = await client.get(SKILLS, params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    skills: list[dict[str, Any]] = resp.json()
    return skills


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    name: str,
    content: bytes,
) -> str:
    resp = await client.post(
        UPLOAD_SIMPLE,
        headers=headers,
        files={"file": (name, io.BytesIO(content), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    return str(resp.json()["id"])


def _named(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    match = [item for item in items if item["name"] == name]
    assert len(match) == 1, f"expected exactly one {name!r} in {[i['name'] for i in items]}"
    return match[0]


# -- GET /assistant/models ----------------------------------------------------


async def test_models_lists_local_plus_own_connections_only(client: AsyncClient) -> None:
    """The model picker always offers the local model, adds each of the user's
    own connections, and never leaks another user's connection (A4).
    """
    a = auth_headers(await register_and_login(client, email="mdl-a@test.com", username="mdla"))
    b = auth_headers(await register_and_login(client, email="mdl-b@test.com", username="mdlb"))

    before = await client.get(MODELS, headers=a)
    assert before.status_code == 200, before.text
    assert [opt["id"] for opt in before.json()] == ["local"]
    assert before.json()[0]["available"] is True
    assert before.json()[0]["label"].startswith("Local (")

    created = await client.post(
        CONNECTIONS,
        json={
            "label": "My Gateway",
            "kind": "openai_compatible",
            "base_url": "http://127.0.0.1:9/v1",
            "model": "gpt-test",
            "secret": "sk-test-not-a-real-key",
        },
        headers=a,
    )
    assert created.status_code == 200, created.text
    connection_id = created.json()["id"]

    # Read back through the assistant picker, not the create response.
    after = await client.get(MODELS, headers=a)
    assert after.status_code == 200, after.text
    options = after.json()
    assert [opt["id"] for opt in options] == ["local", connection_id]
    picked = options[1]
    assert picked["available"] is True  # status "active" on create
    assert picked["label"].startswith("My Gateway")
    assert "gpt-test" in picked["label"]

    # A4: user B's picker still has only the local option.
    other = await client.get(MODELS, headers=b)
    assert other.status_code == 200, other.text
    assert [opt["id"] for opt in other.json()] == ["local"]


# -- GET /assistant/skills ----------------------------------------------------


async def test_skill_list_is_scoped_to_the_owner(client: AsyncClient) -> None:
    """A4: a skill belongs to exactly one user and never shows up for another."""
    a = auth_headers(await register_and_login(client, email="own-a@test.com", username="owna"))
    b = auth_headers(await register_and_login(client, email="own-b@test.com", username="ownb"))
    user_a = await _current_user_id(client, a)

    skill_id = await _seed_skill(user_id=user_a, name="alice_only")

    mine = await _list_skills(client, a)
    assert [s["id"] for s in mine] == [str(skill_id)]
    assert mine[0]["name"] == "alice_only"
    assert mine[0]["status"] == "installed"
    assert mine[0]["chat_enabled"] is False

    assert await _list_skills(client, b) == []
    assert await _list_skills(client, b, status="pending") == []


async def test_skill_list_filters_by_status(client: AsyncClient) -> None:
    """``status`` selects the lifecycle bucket; installed is the default view."""
    h = auth_headers(await register_and_login(client, email="stat@test.com", username="stat"))
    user_id = await _current_user_id(client, h)

    installed_id = await _seed_skill(user_id=user_id, name="ready_skill", status="installed")
    pending_id = await _seed_skill(user_id=user_id, name="draft_skill", status="pending")

    default_view = await _list_skills(client, h)
    assert [s["id"] for s in default_view] == [str(installed_id)]

    installed = await _list_skills(client, h, status="installed")
    assert [s["id"] for s in installed] == [str(installed_id)]

    pending = await _list_skills(client, h, status="pending")
    assert [s["id"] for s in pending] == [str(pending_id)]
    assert pending[0]["name"] == "draft_skill"


# -- POST /assistant/skills/{id}/approve --------------------------------------


async def test_approve_moves_skill_from_pending_to_installed(client: AsyncClient) -> None:
    """Approval is the install gate: the skill must change bucket on read-back."""
    h = auth_headers(await register_and_login(client, email="appr@test.com", username="appr"))
    user_id = await _current_user_id(client, h)
    skill_id = await _seed_skill(user_id=user_id, name="tidy_files", status="pending")

    assert await _list_skills(client, h, status="installed") == []

    resp = await client.post(f"{SKILLS}/{skill_id}/approve", headers=h)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["message"] == "tidy_files installed."
    assert body["skill"]["status"] == "installed"

    installed = await _list_skills(client, h, status="installed")
    assert [s["id"] for s in installed] == [str(skill_id)]
    assert installed[0]["status"] == "installed"
    assert await _list_skills(client, h, status="pending") == []


async def test_approve_rejects_malformed_manifest_and_leaves_skill_pending(
    client: AsyncClient,
) -> None:
    """The manifest is re-validated at the install gate, so a context-menu entry
    pointing at some other skill can never reach the right-click menu.
    """
    h = auth_headers(await register_and_login(client, email="badman@test.com", username="badman"))
    user_id = await _current_user_id(client, h)
    bad = _manifest("good_name", "Does a thing")
    bad["ui"]["context_menu"][0]["handler"] = "some_other_skill"
    skill_id = await _seed_skill(user_id=user_id, name="good_name", status="pending", manifest=bad)

    resp = await client.post(f"{SKILLS}/{skill_id}/approve", headers=h)
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert error["code"] == "INVALID_OPERATION"
    assert "some_other_skill" in error["message"]

    # Read back: still pending, and still absent from the installed view.
    pending = await _list_skills(client, h, status="pending")
    assert [s["id"] for s in pending] == [str(skill_id)]
    assert await _list_skills(client, h, status="installed") == []


# -- POST /assistant/skills/{id}/execute --------------------------------------


async def test_pending_skill_cannot_execute_and_leaves_no_trace(client: AsyncClient) -> None:
    """API-AI-12 (A3): an unapproved skill must not run, must produce no files
    and must not take the pre-write snapshot; after approval the same call runs
    the sandbox and the produced file really lands in the drive.

    NOTE: doc/test-cases.md predicts 403 here, but ``execute_skill`` looks the
    skill up with ``status == installed`` and raises ``NotFoundError``, so the
    endpoint answers 404 -- asserted against the implementation.
    """
    h = auth_headers(await register_and_login(client, email="gate@test.com", username="gate"))
    user_id = await _current_user_id(client, h)
    item_id = await _upload(client, h, "notes.txt", b"hello")
    skill_id = await _seed_skill(user_id=user_id, name="upper_copy", status="pending")

    denied = await client.post(f"{SKILLS}/{skill_id}/execute", json={"item_id": item_id}, headers=h)
    assert denied.status_code == 404, denied.text
    assert denied.json()["error"]["code"] == "NOT_FOUND"

    # A3: no output folder, and no "before write" snapshot was taken.
    assert [item["name"] for item in await _list_items(client, h)] == ["notes.txt"]
    snapshots = await client.get(SNAPSHOTS, headers=h)
    assert snapshots.status_code == 200, snapshots.text
    assert snapshots.json() == []

    approve = await client.post(f"{SKILLS}/{skill_id}/approve", headers=h)
    assert approve.status_code == 200, approve.text

    run = await client.post(f"{SKILLS}/{skill_id}/execute", json={"item_id": item_id}, headers=h)
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["skill_id"] == str(skill_id)
    assert body["skill_name"] == "upper_copy"
    assert body["item_id"] == item_id
    assert body["output"]["produced_files"] == ["upper.txt"]
    assert body["output"]["summary"] == {"written": "upper.txt", "bytes": 5}

    # A3: read the ingested file back out of the drive and check its bytes.
    root = await _list_items(client, h)
    folder = _named(root, "notes (extracted)")
    assert folder["item_type"] == "FOLDER"
    produced = await _list_items(client, h, parent_id=folder["id"])
    assert [item["name"] for item in produced] == ["upper.txt"]
    download = await client.get(f"/api/v1/download/{produced[0]['id']}", headers=h)
    assert download.status_code == 200, download.text
    assert download.content == b"HELLO"

    # A3: the pre-write Time Machine snapshot exists now (and only now).
    after = await client.get(SNAPSHOTS, headers=h)
    assert after.status_code == 200, after.text
    taken = after.json()
    assert [snap["trigger"] for snap in taken] == ["assistant"]
    assert "upper_copy" in taken[0]["label"]


async def test_execute_rejects_an_item_type_the_manifest_does_not_declare(
    client: AsyncClient,
) -> None:
    """DEC-035: a folder-only skill refuses a file, before any sandbox run."""
    h = auth_headers(await register_and_login(client, email="wtype@test.com", username="wtype"))
    user_id = await _current_user_id(client, h)
    item_id = await _upload(client, h, "notes.txt", b"data")
    skill_id = await _seed_skill(
        user_id=user_id,
        name="folder_only",
        description="Archive a folder",
        item_types=["FOLDER"],
    )

    resp = await client.post(f"{SKILLS}/{skill_id}/execute", json={"item_id": item_id}, headers=h)
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert error["code"] == "INVALID_OPERATION"
    assert error["message"] == "This skill runs on a folder"

    # Nothing ran: the drive still holds only the original upload.
    assert [item["name"] for item in await _list_items(client, h)] == ["notes.txt"]


# -- PATCH /assistant/skills/{id} ---------------------------------------------


@pytest.mark.parametrize(
    ("bad_code", "expected_fragment"),
    [
        pytest.param(
            "import subprocess\n\n\ndef run(input_path, output_dir, params):\n"
            "    return {'ok': True}\n",
            "forbidden import: subprocess",
            id="forbidden-import",
        ),
        pytest.param(
            "def run(input_path, output_dir, params):\n    return eval(params['expr'])\n",
            "forbidden use of 'eval'",
            id="eval",
        ),
        pytest.param(
            "def run(input_path, output_dir, params):\n"
            "    return {'cls': params.__class__.__name__}\n",
            "forbidden dunder access: __class__",
            id="dunder",
        ),
        pytest.param(
            "def go(input_path, output_dir, params):\n    return {}\n",
            "missing required entrypoint",
            id="no-run-entrypoint",
        ),
    ],
)
async def test_codeguard_rejects_dangerous_edits_and_keeps_stored_code(
    client: AsyncClient,
    bad_code: str,
    expected_fragment: str,
) -> None:
    """API-AI-11: a hand edit must not slip past the static scan, and a rejected
    edit must leave the previously stored code untouched (verified by re-reading
    the skill through ``GET /assistant/skills``).
    """
    h = auth_headers(await register_and_login(client, email="guard@test.com", username="guard"))
    user_id = await _current_user_id(client, h)
    skill_id = await _seed_skill(user_id=user_id, name="edit_me")

    resp = await client.patch(f"{SKILLS}/{skill_id}", json={"code": bad_code}, headers=h)
    assert resp.status_code == 400, resp.text
    error = resp.json()["error"]
    assert error["code"] == "INVALID_OPERATION"
    assert error["message"].startswith("Edited code failed validation:")
    assert expected_fragment in error["message"]

    stored = await _list_skills(client, h)
    assert len(stored) == 1
    assert stored[0]["code"] == UPPERCASE_CODE


async def test_valid_code_edit_is_persisted_and_changes_what_runs(client: AsyncClient) -> None:
    """A3: an accepted edit is stored AND is the code the sandbox actually runs
    -- proven by the bytes of the file the skill produced.
    """
    h = auth_headers(await register_and_login(client, email="edit@test.com", username="edit"))
    user_id = await _current_user_id(client, h)
    item_id = await _upload(client, h, "notes.txt", b"abcd")
    skill_id = await _seed_skill(user_id=user_id, name="transform")

    patched = await client.patch(f"{SKILLS}/{skill_id}", json={"code": REVERSE_CODE}, headers=h)
    assert patched.status_code == 200, patched.text
    assert patched.json()["code"] == REVERSE_CODE

    stored = await _list_skills(client, h)
    assert stored[0]["code"] == REVERSE_CODE
    assert stored[0]["description"] == "Uppercase a file"  # untouched by a code-only edit

    run = await client.post(f"{SKILLS}/{skill_id}/execute", json={"item_id": item_id}, headers=h)
    assert run.status_code == 200, run.text
    assert run.json()["output"]["produced_files"] == ["reversed.txt"]

    folder = _named(await _list_items(client, h), "notes (extracted)")
    produced = await _list_items(client, h, parent_id=folder["id"])
    assert [item["name"] for item in produced] == ["reversed.txt"]
    download = await client.get(f"/api/v1/download/{produced[0]['id']}", headers=h)
    assert download.status_code == 200, download.text
    assert download.content == b"dcba"


async def test_description_edit_also_rewrites_the_manifest_description(
    client: AsyncClient,
) -> None:
    """The manifest is what the right-click menu reads, so it must track the
    edited description rather than keep the stale one.
    """
    h = auth_headers(await register_and_login(client, email="desc@test.com", username="desc"))
    user_id = await _current_user_id(client, h)
    skill_id = await _seed_skill(user_id=user_id, name="described")

    resp = await client.patch(
        f"{SKILLS}/{skill_id}", json={"description": "Shout the file"}, headers=h
    )
    assert resp.status_code == 200, resp.text

    stored = await _list_skills(client, h)
    assert len(stored) == 1
    assert stored[0]["description"] == "Shout the file"
    assert stored[0]["manifest"]["description"] == "Shout the file"
    assert stored[0]["manifest"]["name"] == "described"
    assert stored[0]["code"] == UPPERCASE_CODE  # code-free edit leaves code alone


async def test_chat_enabled_toggle_persists_both_ways(client: AsyncClient) -> None:
    """The "usable from chat" opt-in must survive the request that set it, in
    both directions (it is what puts a self-built skill in front of the planner).
    """
    h = auth_headers(await register_and_login(client, email="chaten@test.com", username="chaten"))
    user_id = await _current_user_id(client, h)
    skill_id = await _seed_skill(user_id=user_id, name="chat_ready")

    on = await client.patch(f"{SKILLS}/{skill_id}", json={"chat_enabled": True}, headers=h)
    assert on.status_code == 200, on.text
    assert on.json()["chat_enabled"] is True

    stored = await _list_skills(client, h)
    assert stored[0]["chat_enabled"] is True
    assert stored[0]["code"] == UPPERCASE_CODE  # toggle-only edit changes nothing else

    off = await client.patch(f"{SKILLS}/{skill_id}", json={"chat_enabled": False}, headers=h)
    assert off.status_code == 200, off.text
    assert off.json()["chat_enabled"] is False

    stored_again = await _list_skills(client, h)
    assert stored_again[0]["chat_enabled"] is False


# -- DELETE /assistant/skills/{id} --------------------------------------------


async def test_delete_removes_the_skill_and_second_delete_is_404(client: AsyncClient) -> None:
    h = auth_headers(await register_and_login(client, email="del@test.com", username="del"))
    user_id = await _current_user_id(client, h)
    skill_id = await _seed_skill(user_id=user_id, name="disposable")

    first = await client.delete(f"{SKILLS}/{skill_id}", headers=h)
    assert first.status_code == 204, first.text

    assert await _list_skills(client, h) == []
    assert await _list_skills(client, h, status="pending") == []

    second = await client.delete(f"{SKILLS}/{skill_id}", headers=h)
    assert second.status_code == 404, second.text
    assert second.json()["error"]["code"] == "NOT_FOUND"


# -- Cross-user isolation (A4) ------------------------------------------------


async def test_non_owner_cannot_edit_approve_execute_or_delete_a_skill(
    client: AsyncClient,
) -> None:
    """A4: every skill mutation is scoped to the owner. B holds a valid token and
    a file of its own, and still gets 404 on all four verbs; A's skill is then
    re-read to prove nothing changed.
    """
    a = auth_headers(await register_and_login(client, email="iso-a@test.com", username="isoa"))
    b = auth_headers(await register_and_login(client, email="iso-b@test.com", username="isob"))
    user_a = await _current_user_id(client, a)
    b_item_id = await _upload(client, b, "b-notes.txt", b"bob")
    skill_id = await _seed_skill(user_id=user_a, name="alice_skill", status="pending")

    patched = await client.patch(
        f"{SKILLS}/{skill_id}", json={"description": "hijacked"}, headers=b
    )
    assert patched.status_code == 404, patched.text

    approved = await client.post(f"{SKILLS}/{skill_id}/approve", headers=b)
    assert approved.status_code == 404, approved.text

    executed = await client.post(
        f"{SKILLS}/{skill_id}/execute", json={"item_id": b_item_id}, headers=b
    )
    assert executed.status_code == 404, executed.text

    deleted = await client.delete(f"{SKILLS}/{skill_id}", headers=b)
    assert deleted.status_code == 404, deleted.text

    # A's skill is intact: still pending, still its original description.
    mine = await _list_skills(client, a, status="pending")
    assert [s["id"] for s in mine] == [str(skill_id)]
    assert mine[0]["description"] == "Uppercase a file"
    assert mine[0]["status"] == "pending"

    # B's own drive is untouched too (no output folder was created).
    assert [item["name"] for item in await _list_items(client, b)] == ["b-notes.txt"]


# -- Model-free authoring path (chat -> pending -> approve -> execute) --------


async def test_context_menu_proposal_flows_from_chat_to_execution(client: AsyncClient) -> None:
    """The inspect-details proposal is hardcoded, so ``POST /assistant/chat``
    reaches it without any model call: the whole propose -> approve -> execute
    round trip is exercised through the public API.

    Skipped only when the assistant feature flag is off (503), which is a
    deployment choice, not a failure.
    """
    h = auth_headers(await register_and_login(client, email="auth1@test.com", username="auth1"))

    chat = await client.post(
        CHAT,
        json={"message": "Add a right-click context menu action to inspect details of an item."},
        headers=h,
    )
    if chat.status_code == 503:
        pytest.skip("assistant disabled on this deployment (ASSISTANT_ENABLED=false)")
    assert chat.status_code == 200, chat.text
    proposal = chat.json()["skill_proposal"]
    assert proposal is not None, chat.json()
    assert proposal["name"] == "inspect_item_details"
    assert proposal["status"] == "pending"

    # Read back: the proposal was persisted as pending, not auto-installed.
    pending = await _list_skills(client, h, status="pending")
    assert [s["name"] for s in pending] == ["inspect_item_details"]
    assert await _list_skills(client, h, status="installed") == []

    skill_id = proposal["id"]
    approve = await client.post(f"{SKILLS}/{skill_id}/approve", headers=h)
    assert approve.status_code == 200, approve.text
    assert approve.json()["message"] == "inspect_item_details installed."

    installed = await _list_skills(client, h, status="installed")
    assert [s["name"] for s in installed] == ["inspect_item_details"]
    menu = installed[0]["manifest"]["ui"]["context_menu"]
    assert menu[0]["handler"] == "inspect_item_details"
    assert sorted(menu[0]["item_types"]) == ["FILE", "FOLDER"]

    folder = await client.post(DRIVE_FOLDERS, json={"name": "Reports"}, headers=h)
    assert folder.status_code == 201, folder.text
    folder_id = folder.json()["id"]

    run = await client.post(f"{SKILLS}/{skill_id}/execute", json={"item_id": folder_id}, headers=h)
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["message"] == "Details for Reports"
    assert body["output"]["name"] == "Reports"
    assert body["output"]["item_type"] == "FOLDER"
    assert body["output"]["is_deleted"] is False
