from __future__ import annotations

from app.assistant.llm.client import LLMMessage


class ContextManager:
    def __init__(self, *, num_ctx: int) -> None:
        self._max_chars = max(1024, num_ctx * 4)

    def trim(self, messages: list[LLMMessage]) -> list[LLMMessage]:
        if not messages:
            return []
        system_messages = [m for m in messages if m.role == "system"]
        non_system = [m for m in messages if m.role != "system"]

        selected: list[LLMMessage] = []
        used = sum(len(m.content) for m in system_messages)
        for message in reversed(non_system):
            length = len(message.content)
            if selected and used + length > self._max_chars:
                break
            selected.append(message)
            used += length
        selected.reverse()
        return [*system_messages, *selected]
