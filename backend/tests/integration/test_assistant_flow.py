"""End-to-end assistant tests against a real Postgres and the real Gemma model.

These stand in for manually driving the in-app AI agent through a browser:
they exercise the full HTTP stack -> planner -> permission gate -> executor ->
real database, and then assert the side effects actually landed.

The chat-driven tests call the *real* configured model (Gemma via Ollama). If
the model is unreachable, ``/chat`` returns 503 and these tests FAIL (they do
not skip) — an unreachable agent is a real failure, by design. The save/rerun
and isolation tests are model-independent and deterministic.

Requires Postgres (see tests/integration/conftest.py) and a reachable
``LLM_BASE_URL`` / ``ASSISTANT_MODEL``.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import auth_headers, register_and_login

pytestmark = pytest.mark.asyncio

CHAT = "/api/v1/assistant/chat"
SESSIONS = "/api/v1/assistant/sessions"
SAVE = "/api/v1/assistant/workflows/save"
SAVED = "/api/v1/assistant/workflows/saved"
DRIVE_ITEMS = "/api/v1/drive/items"


async def _root_folder_names(client: AsyncClient, headers: dict[str, str]) -> list[str]:
    resp = await client.get(DRIVE_ITEMS, headers=headers)
    assert resp.status_code == 200, resp.text
    return [item["name"] for item in resp.json()["items"]]


# ── Real-model end-to-end (require a reachable Gemma) ──────────────────────────


@pytest.mark.needs_llm
async def test_chat_persists_session_and_messages(client: AsyncClient) -> None:
    """A real chat turn must land a session + the user/assistant messages in the DB."""
    h = auth_headers(await register_and_login(client, email="agent1@test.com", username="agent1"))
    prompt = "How much storage space do I have left?"

    chat = await client.post(CHAT, json={"message": prompt}, headers=h)
    # 503 here means the configured Gemma model was unreachable -> real failure.
    assert chat.status_code == 200, chat.text
    session_id = chat.json()["session_id"]

    sessions = await client.get(SESSIONS, headers=h)
    assert sessions.status_code == 200
    assert session_id in [s["id"] for s in sessions.json()]

    messages = await client.get(f"{SESSIONS}/{session_id}/messages", headers=h)
    assert messages.status_code == 200
    body = messages.json()
    assert [m["role"] for m in body] == ["user", "assistant"]
    assert body[0]["content"] == prompt
    assert body[1]["content"]  # the assistant said something


@pytest.mark.needs_llm
async def test_chat_create_folder_pending_confirm_creates_real_item(
    client: AsyncClient,
) -> None:
    """The agent should plan a folder creation, gate it for approval, and on
    confirm the folder must actually exist in the drive."""
    h = auth_headers(await register_and_login(client, email="agent2@test.com", username="agent2"))
    folder_name = f"AgentFolder_{uuid4().hex[:8]}"

    chat = await client.post(
        CHAT,
        json={"message": f'Create a new folder named "{folder_name}".'},
        headers=h,
    )
    assert chat.status_code == 200, chat.text
    plan = chat.json().get("plan")
    assert plan is not None, f"model produced no actionable plan: {chat.json()}"

    # Folder creation is a write action -> it must be gated, not auto-run.
    if plan["status"] == "pending_approval":
        workflow_id = plan["workflow_id"]
        confirm = await client.post(f"/api/v1/assistant/workflows/{workflow_id}/confirm", headers=h)
        assert confirm.status_code == 200, confirm.text
        assert confirm.json()["status"] == "executed"

    assert folder_name in await _root_folder_names(client, h), (
        "agent did not create the requested folder"
    )


# ── Deterministic flows (no model needed) ─────────────────────────────────────


async def test_save_and_rerun_workflow_executes_and_persists(client: AsyncClient) -> None:
    h = auth_headers(await register_and_login(client, email="agent3@test.com", username="agent3"))
    folder_name = f"Saved_{uuid4().hex[:8]}"

    save = await client.post(
        SAVE,
        json={
            "name": "make report folder",
            "source_nl": "create the report folder",
            "steps": [{"skill": "create_folder", "arguments": {"name": folder_name}}],
        },
        headers=h,
    )
    assert save.status_code == 200, save.text
    workflow_id = save.json()["id"]
    assert save.json()["name"] == "make report folder"

    saved = await client.get(SAVED, headers=h)
    assert saved.status_code == 200
    assert workflow_id in [w["id"] for w in saved.json()]

    rerun = await client.post(f"{SAVED}/{workflow_id}/rerun", headers=h)
    assert rerun.status_code == 200, rerun.text
    assert rerun.json()["status"] == "executed"
    assert rerun.json()["results"][0]["ok"] is True

    assert folder_name in await _root_folder_names(client, h)


async def test_save_rejects_unknown_skill(client: AsyncClient) -> None:
    h = auth_headers(await register_and_login(client, email="agent4@test.com", username="agent4"))

    resp = await client.post(
        SAVE,
        json={"name": "bad", "steps": [{"skill": "not_a_real_skill", "arguments": {}}]},
        headers=h,
    )
    assert resp.status_code == 400, resp.text
    assert "INVALID_OPERATION" in resp.json()["error"]["code"]


async def test_saved_workflows_are_isolated_between_users(client: AsyncClient) -> None:
    a = auth_headers(await register_and_login(client, email="ua@test.com", username="ua"))
    b = auth_headers(await register_and_login(client, email="ub@test.com", username="ub"))

    save = await client.post(
        SAVE,
        json={"name": "a-only", "steps": [{"skill": "create_folder", "arguments": {"name": "X"}}]},
        headers=a,
    )
    assert save.status_code == 200, save.text
    workflow_id = save.json()["id"]

    # B sees none of A's saved workflows...
    saved_b = await client.get(SAVED, headers=b)
    assert saved_b.status_code == 200
    assert saved_b.json() == []

    # ...and cannot rerun one it does not own.
    rerun_b = await client.post(f"{SAVED}/{workflow_id}/rerun", headers=b)
    assert rerun_b.status_code == 404, rerun_b.text


@pytest.mark.needs_llm
async def test_sessions_are_isolated_between_users(client: AsyncClient) -> None:
    """A's conversation must never appear in B's session list or be readable by B."""
    a = auth_headers(await register_and_login(client, email="sa@test.com", username="sa"))
    b = auth_headers(await register_and_login(client, email="sb@test.com", username="sb"))

    chat = await client.post(CHAT, json={"message": "List my files please."}, headers=a)
    assert chat.status_code == 200, chat.text
    a_session_id = chat.json()["session_id"]

    sessions_b = await client.get(SESSIONS, headers=b)
    assert sessions_b.status_code == 200
    assert a_session_id not in [s["id"] for s in sessions_b.json()]

    # B asking for A's transcript gets nothing (ownership-scoped).
    messages_b = await client.get(f"{SESSIONS}/{a_session_id}/messages", headers=b)
    assert messages_b.status_code == 200
    assert messages_b.json() == []
