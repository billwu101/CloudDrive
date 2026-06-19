from __future__ import annotations

import os

import pytest

from app.assistant.llm.client import ExternalAuthError, LLMMessage, LLMUnavailableError
from app.external_model.codex_client import CodexSubscriptionClient, _extract_response

_FRAMED = (
    "OpenAI Codex v0.141\n--------\nworkdir: /x\n--------\nuser\nhi\ncodex\n{}\ntokens used 30\n"
)


async def test_chat_writes_auth_and_returns_extracted_content() -> None:
    seen: dict[str, object] = {}

    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        home = env["CODEX_HOME"]
        with open(os.path.join(home, "auth.json"), encoding="utf-8") as fh:
            seen["auth"] = fh.read()
        seen["cmd"] = cmd
        return 0, _FRAMED.replace("{}", '{"reply":"ok"}')

    client = CodexSubscriptionClient(auth_json='{"tokens":{"access_token":"a"}}', runner=runner)
    resp = await client.chat(
        [LLMMessage(role="system", content="sys"), LLMMessage(role="user", content="hi")],
        [],
        num_ctx=1000,
    )

    assert resp.content == '{"reply":"ok"}'  # extracted from the codex framing
    assert seen["auth"] == '{"tokens":{"access_token":"a"}}'  # decrypted token written to home
    cmd = seen["cmd"]
    assert isinstance(cmd, list)
    assert "exec" in cmd and "--skip-git-repo-check" in cmd
    assert "sys" in cmd[-1] and "hi" in cmd[-1]  # messages flattened into the prompt


async def test_auth_failure_raises_external_auth_error() -> None:
    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        return 1, "Error: not logged in. Please sign in."

    client = CodexSubscriptionClient(auth_json="{}", runner=runner)
    with pytest.raises(ExternalAuthError):
        await client.chat([LLMMessage(role="user", content="x")], [], num_ctx=10)


async def test_other_failure_is_unavailable() -> None:
    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        return 1, "some transient network error"

    client = CodexSubscriptionClient(auth_json="{}", runner=runner)
    with pytest.raises(LLMUnavailableError):
        await client.chat([LLMMessage(role="user", content="x")], [], num_ctx=10)


async def test_refreshed_token_is_persisted_and_home_wiped() -> None:
    refreshed: list[str] = []
    homes: list[str] = []

    async def runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
        home = env["CODEX_HOME"]
        homes.append(home)
        # Simulate the CLI refreshing the token mid-call.
        with open(os.path.join(home, "auth.json"), "w", encoding="utf-8") as fh:
            fh.write('{"tokens":{"access_token":"NEW"}}')
        return 0, _FRAMED

    async def on_refreshed(new_auth: str) -> None:
        refreshed.append(new_auth)

    client = CodexSubscriptionClient(
        auth_json='{"tokens":{"access_token":"OLD"}}', runner=runner, on_refreshed=on_refreshed
    )
    await client.chat([LLMMessage(role="user", content="x")], [], num_ctx=10)

    assert refreshed == ['{"tokens":{"access_token":"NEW"}}']  # new token handed back
    assert not os.path.exists(homes[0])  # throwaway home wiped


def test_extract_response_without_framing_returns_whole_output() -> None:
    assert _extract_response("just some text") == "just some text"
