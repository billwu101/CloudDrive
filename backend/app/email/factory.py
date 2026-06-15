from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.email.base import EmailProvider
from app.email.console import ConsoleEmailProvider
from app.email.smtp import SMTPEmailProvider

logger = logging.getLogger("app.email")


def get_email_provider(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmailProvider:
    """Return the configured EmailProvider.

    "smtp" requires smtp_host to be set; otherwise we fall back to the console
    provider so the app never crashes on a half-configured environment.
    """
    if settings.email_provider == "smtp":
        if not settings.smtp_host:
            logger.warning(
                "EMAIL_PROVIDER=smtp but SMTP_HOST is empty; falling back to console email provider"
            )
            return ConsoleEmailProvider()
        return SMTPEmailProvider(
            host=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username,
            password=settings.smtp_password,
            sender=settings.smtp_from,
            use_tls=settings.smtp_use_tls,
        )
    return ConsoleEmailProvider()


EmailProviderDep = Annotated[EmailProvider, Depends(get_email_provider)]
