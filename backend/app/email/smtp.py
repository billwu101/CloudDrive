from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

logger = logging.getLogger("app.email")


class SMTPEmailProvider:
    """Send email via an SMTP server (e.g. Gmail with an App Password)."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_tls: bool,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls

    async def send(self, *, to: str, subject: str, body: str) -> None:
        message = EmailMessage()
        message["From"] = self._sender
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)

        try:
            await aiosmtplib.send(
                message,
                hostname=self._host,
                port=self._port,
                username=self._username or None,
                password=self._password or None,
                start_tls=self._use_tls,
            )
        except Exception:
            # Delivery failures must not leak via the API: swallow and log so the
            # forgot-password endpoint stays non-enumerable and returns the same
            # response whether or not delivery succeeds.
            logger.exception("[email:smtp] failed to send to %s", to)
