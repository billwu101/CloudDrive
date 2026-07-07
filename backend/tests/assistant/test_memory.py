from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.assistant.memory import (
    append_result_summary,
    history_to_messages,
    summarise_results,
)
from app.assistant.workflow import StepResult
from app.models.assistant_session import AssistantMessage


def _msg(role: str, content: str) -> AssistantMessage:
    return AssistantMessage(
        id=uuid4(),
        session_id=uuid4(),
        role=role,
        content=content,
        tool_calls=[],
        created_at=datetime.now(UTC),
    )


def test_summarise_results_marks_status_and_keeps_output() -> None:
    summary = summarise_results(
        [
            StepResult(index=0, skill="list_items", ok=True, output=["budget.xlsx", "notes.txt"]),
            StepResult(index=1, skill="rename_item", ok=False, error="not found"),
            StepResult(index=2, skill="trash_item", ok=False, skipped=True),
        ]
    )
    assert summary.startswith("[executed] ")
    assert "list_items: ok → " in summary
    assert "budget.xlsx" in summary  # key identifier survives for later reference
    assert "rename_item: failed error=not found" in summary
    assert "trash_item: skipped" in summary


def test_summarise_results_truncates_long_output() -> None:
    summary = summarise_results(
        [StepResult(index=0, skill="list_items", ok=True, output="x" * 500)]
    )
    assert "…" in summary
    assert len(summary) < 300  # bounded, not the full 500-char payload


def test_summarise_results_empty_is_blank() -> None:
    assert summarise_results([]) == ""


def test_append_result_summary_joins_reply_and_summary() -> None:
    combined = append_result_summary(
        "Done.", [StepResult(index=0, skill="list_items", ok=True, output=["a.txt"])]
    )
    assert combined.startswith("Done.\n\n[executed] ")
    assert "a.txt" in combined


def test_append_result_summary_returns_reply_when_no_results() -> None:
    assert append_result_summary("Just chatting.", []) == "Just chatting."


def test_history_to_messages_takes_last_n_user_assistant() -> None:
    messages = [
        _msg("user", "u1"),
        _msg("assistant", "a1"),
        _msg("user", "u2"),
        _msg("assistant", "a2"),
    ]
    history = history_to_messages(messages, max_messages=3)
    assert [(m.role, m.content) for m in history] == [
        ("assistant", "a1"),
        ("user", "u2"),
        ("assistant", "a2"),
    ]


def test_history_to_messages_drops_other_roles_and_empty() -> None:
    messages = [
        _msg("system", "sys"),  # non user/assistant → dropped
        _msg("user", ""),  # empty → dropped
        _msg("tool", "toolstuff"),  # non user/assistant → dropped
        _msg("assistant", "a1"),
    ]
    history = history_to_messages(messages, max_messages=10)
    assert [(m.role, m.content) for m in history] == [("assistant", "a1")]


def test_history_to_messages_zero_disables_memory() -> None:
    assert history_to_messages([_msg("user", "u1")], max_messages=0) == []
