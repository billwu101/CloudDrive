from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
from collections.abc import Awaitable, Callable
from typing import Any

from app.assistant.llm.client import (
    ExternalAuthError,
    LLMMessage,
    LLMResponse,
    LLMToolDefinition,
    LLMUnavailableError,
)

logger = logging.getLogger("app.external_model.codex")

# (cmd, env, timeout) -> (returncode, combined stdout+stderr). Injectable for tests.
SubprocessRunner = Callable[[list[str], dict[str, str], float], Awaitable[tuple[int, str]]]


async def _default_runner(cmd: list[str], env: dict[str, str], timeout: float) -> tuple[int, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise LLMUnavailableError("Codex subscription call timed out") from exc
    return proc.returncode or 0, stdout.decode("utf-8", errors="replace")


class CodexSubscriptionClient:
    """Calls GPT-5.5 via a user's Codex subscription by bridging the official
    `codex` CLI (DEC-026 / external-model-integration.md §2.1).

    Each call writes the (decrypted) auth.json into a throwaway isolated
    ``CODEX_HOME``, runs ``codex exec`` against it, then wipes the dir. If the CLI
    refreshed the token, the new auth.json is handed back via ``on_refreshed`` to
    be re-encrypted and stored. planner/codegen consume ``content`` (JSON), so the
    CLI's text output maps cleanly onto an LLMResponse.
    """

    def __init__(
        self,
        *,
        auth_json: str,
        model: str = "gpt-5.5",
        codex_bin: str = "codex",
        timeout: float = 120.0,
        runner: SubprocessRunner | None = None,
        on_refreshed: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._auth_json = auth_json
        self._model = model
        self._codex_bin = codex_bin
        self._timeout = timeout
        self._runner = runner or _default_runner
        self._on_refreshed = on_refreshed

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        # response_format (structured output) isn't expressible through the codex
        # CLI bridge, so it's accepted for interface parity and ignored here.
        home = tempfile.mkdtemp(prefix="codex_home_")
        try:
            auth_path = os.path.join(home, "auth.json")
            with open(auth_path, "w", encoding="utf-8") as fh:
                fh.write(self._auth_json)
            os.chmod(auth_path, 0o600)

            cmd = [self._codex_bin, "exec", "--skip-git-repo-check", _messages_to_prompt(messages)]
            env = {**os.environ, "CODEX_HOME": home}
            returncode, output = await self._runner(cmd, env, self._timeout)

            if returncode != 0:
                if _is_auth_failure(output):
                    raise ExternalAuthError("Codex subscription credential was rejected")
                raise LLMUnavailableError(f"Codex subscription call failed (exit {returncode})")

            await self._persist_refresh(auth_path)
            return LLMResponse(content=_extract_response(output), tool_calls=[], model=self._model)
        finally:
            shutil.rmtree(home, ignore_errors=True)

    async def _persist_refresh(self, auth_path: str) -> None:
        if self._on_refreshed is None:
            return
        try:
            with open(auth_path, encoding="utf-8") as fh:
                after = fh.read()
        except OSError:
            return
        if after.strip() and after.strip() != self._auth_json.strip():
            try:
                await self._on_refreshed(after)
            except Exception:
                logger.exception("failed to persist refreshed codex token")


def _messages_to_prompt(messages: list[LLMMessage]) -> str:
    """Flatten the chat messages into a single prompt for `codex exec`."""
    return "\n\n".join(m.content for m in messages if m.content).strip()


def _extract_response(output: str) -> str:
    """Pull the assistant's reply out of `codex exec` output. The CLI frames the
    reply after a `codex` line and before a `tokens used` line; fall back to the
    whole output if the framing isn't present."""
    if "\ncodex\n" in output:
        tail = output.rsplit("\ncodex\n", 1)[-1]
        tail = re.split(r"\ntokens used\b", tail)[0]
        return tail.strip()
    return output.strip()


def _is_auth_failure(output: str) -> bool:
    low = output.lower()
    return any(
        marker in low
        for marker in (
            "not logged in",
            "unauthor",
            "401",
            "403",
            "re-authenticate",
            "please sign in",
            "invalid_grant",
            "token expired",
            "expired token",
        )
    )
