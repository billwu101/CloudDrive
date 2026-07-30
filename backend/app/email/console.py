from __future__ import annotations

import logging

logger = logging.getLogger("app.email")


class ConsoleEmailProvider:
    """Email provider that logs messages instead of sending them.

    Default in development so the password-reset flow works without any SMTP
    configuration — the generated password appears in the server log.
    """

    async def send(self, *, to: str, subject: str, body: str) -> None:
        # WARNING, not INFO: an INFO line reads like "sent". Nothing was sent —
        # the message is printed here and discarded.
        logger.warning(
            "[email:NOT-DELIVERED] no mailer configured; message discarded. to=%s subject=%s\n%s",
            to,
            subject,
            body,
        )
