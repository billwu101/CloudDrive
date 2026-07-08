"""Conversation memory helpers (proposal-assistant-memory).

Two pure, independently testable pieces used to give the planner multi-turn
context:

- ``summarise_results`` compresses a turn's StepResults into a short text line
  that is appended to the persisted assistant message content. Tool results are
  carried as assistant *text* (never a ``tool``-role message: a real-model A/B on
  gemma4 showed the tool role is not digested — 0/4 vs 4/4 for assistant text).
- ``history_to_messages`` maps the most recent stored messages into the
  ``LLMMessage`` list the planner replays as context.
"""

from __future__ import annotations

from app.assistant.llm.client import LLMMessage
from app.assistant.workflow import StepResult
from app.models.assistant_session import AssistantMessage

# Cap each step's serialized output so a large payload (e.g. a long file listing)
# cannot dominate the context budget; the head keeps the useful identifiers.
_MAX_OUTPUT_CHARS = 200


def summarise_results(results: list[StepResult]) -> str:
    """A compact one-line-per-step summary, or "" when there is nothing to add.

    Carries the key identifiers (skill, ok/fail, truncated output) so a follow-up
    turn can resolve references like "the first one" against what actually ran.
    """
    lines: list[str] = []
    for result in results:
        if result.skipped:
            status = "skipped"
        elif result.ok:
            status = "ok"
        else:
            status = "failed"
        detail = ""
        if result.error:
            detail = f" error={_truncate(result.error)}"
        elif result.output is not None:
            detail = f" → {_truncate(str(result.output))}"
        lines.append(f"{result.skill}: {status}{detail}")
    if not lines:
        return ""
    return "[executed] " + "; ".join(lines)


def append_result_summary(reply: str, results: list[StepResult]) -> str:
    """The reply text to persist: the model's reply plus the result summary.

    Kept separate from the live ``response.message`` on purpose — the live turn
    already renders results as a table, so only the *stored* content carries the
    summary (visible on reload, and replayed to the model next turn).
    """
    summary = summarise_results(results)
    if not summary:
        return reply
    return f"{reply}\n\n{summary}" if reply else summary


def history_to_messages(messages: list[AssistantMessage], *, max_messages: int) -> list[LLMMessage]:
    """Most-recent ``max_messages`` user/assistant turns as replayable context.

    ``max_messages <= 0`` disables memory. Non user/assistant rows are dropped;
    empty-content rows are skipped so a placeholder never displaces real context.
    """
    if max_messages <= 0:
        return []
    history: list[LLMMessage] = []
    for message in messages:
        if not message.content:
            continue
        if message.role == "user":
            history.append(LLMMessage(role="user", content=message.content))
        elif message.role == "assistant":
            history.append(LLMMessage(role="assistant", content=message.content))
    return history[-max_messages:]


def _truncate(text: str) -> str:
    text = text.strip()
    if len(text) <= _MAX_OUTPUT_CHARS:
        return text
    return text[:_MAX_OUTPUT_CHARS] + "…"
