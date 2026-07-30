"""Whether outbound mail will actually leave the building.

The password-reset flow is deliberately non-enumerable: it returns the same
response whether or not delivery succeeded. That is right for security and
terrible for operations — a misconfigured mailer looks exactly like a working
one from the outside. These helpers make the difference visible on the inside.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.config import Settings

logger = logging.getLogger("app.email")


@dataclass(frozen=True)
class MailDelivery:
    """What the current configuration will actually do with an email."""

    provider: str  # what is configured
    effective: str  # what will really run ("console" | "smtp")
    delivers: bool  # False = mail is logged and thrown away

    @property
    def reason(self) -> str | None:
        if self.delivers:
            return None
        if self.provider != "smtp":
            return "EMAIL_PROVIDER is not 'smtp'"
        return "EMAIL_PROVIDER=smtp but SMTP_HOST is empty"


def describe_delivery(settings: Settings) -> MailDelivery:
    """Resolve config the same way `get_email_provider` does."""
    if settings.email_provider == "smtp" and settings.smtp_host:
        return MailDelivery(provider=settings.email_provider, effective="smtp", delivers=True)
    return MailDelivery(provider=settings.email_provider, effective="console", delivers=False)


def check_mail_on_startup(settings: Settings) -> MailDelivery:
    """Say plainly, at boot, whether password-reset mail can reach anyone.

    Loud in production because there the failure is invisible and total: users
    request a reset, are told to check their inbox, and nothing was ever sent.
    """
    delivery = describe_delivery(settings)
    if delivery.delivers:
        logger.info(
            "email: delivering via SMTP host=%s port=%s", settings.smtp_host, settings.smtp_port
        )
    elif settings.app_env == "production":
        logger.error(
            "email: NOT DELIVERING — %s. Password reset is silently broken: users will be "
            "told a temporary password was sent, but nothing leaves this server. Set "
            "EMAIL_PROVIDER=smtp and SMTP_HOST to fix.",
            delivery.reason,
        )
    else:
        logger.warning(
            "email: not delivering (%s) — messages are written to this log only. "
            "Fine for development; set SMTP_HOST to send for real.",
            delivery.reason,
        )
    return delivery
