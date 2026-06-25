from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

LLMRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class LLMMessage:
    role: LLMRole
    content: str


@dataclass(frozen=True)
class LLMToolDefinition:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class LLMToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LLMResponse:
    content: str
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    model: str | None = None


class LLMClientError(Exception):
    """Base error for assistant LLM failures."""


class LLMUnavailableError(LLMClientError):
    """Raised when no eligible model can produce a response."""


class LLMInvalidResponseError(LLMClientError):
    """Raised when a provider response cannot be parsed."""


class ExternalAuthError(LLMClientError):
    """Raised when an external provider rejects the credential itself — an invalid
    key or an exhausted quota — as opposed to a transient outage. Signals that the
    stored credential should be marked invalid."""


class LLMClient(Protocol):
    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse: ...
