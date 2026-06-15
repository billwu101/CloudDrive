from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmailProvider(Protocol):
    """Protocol for pluggable transactional-email backends."""

    async def send(self, *, to: str, subject: str, body: str) -> None:
        """Deliver a plain-text email. Implementations must not raise on
        recoverable delivery problems that should be logged rather than
        surfaced to the caller (the password-reset flow must stay
        non-enumerable)."""
        ...
