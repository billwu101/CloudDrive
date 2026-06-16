from __future__ import annotations

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage


def test_context_trim_keeps_system_and_newest_messages() -> None:
    manager = ContextManager(num_ctx=256)
    messages = [
        LLMMessage(role="system", content="system rules"),
        LLMMessage(role="user", content="old" * 1000),
        LLMMessage(role="assistant", content="new answer"),
        LLMMessage(role="user", content="new question"),
    ]

    trimmed = manager.trim(messages)

    assert trimmed[0].role == "system"
    assert [m.content for m in trimmed] == ["system rules", "new answer", "new question"]
