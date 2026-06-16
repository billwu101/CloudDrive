from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AssistantRole = Literal["system", "user", "assistant", "tool"]


class AssistantChatRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


class AssistantToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantToolResult(BaseModel):
    name: str
    ok: bool
    output: Any | None = None
    error: str | None = None


class AssistantChatResponse(BaseModel):
    session_id: UUID
    message: str
    tool_calls: list[AssistantToolCall] = Field(default_factory=list)
    tool_results: list[AssistantToolResult] = Field(default_factory=list)
