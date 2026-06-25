from __future__ import annotations

import logging

import pytest

from app.core.config import Settings
from app.email.console import ConsoleEmailProvider
from app.email.factory import get_email_provider
from app.email.smtp import SMTPEmailProvider


def _settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]


def test_default_provider_is_console() -> None:
    provider = get_email_provider(_settings())
    assert isinstance(provider, ConsoleEmailProvider)


def test_smtp_provider_selected_when_configured() -> None:
    provider = get_email_provider(_settings(email_provider="smtp", smtp_host="smtp.example.com"))
    assert isinstance(provider, SMTPEmailProvider)


def test_smtp_without_host_falls_back_to_console() -> None:
    provider = get_email_provider(_settings(email_provider="smtp", smtp_host=""))
    assert isinstance(provider, ConsoleEmailProvider)


async def test_console_provider_logs_message(caplog: pytest.LogCaptureFixture) -> None:
    provider = ConsoleEmailProvider()
    with caplog.at_level(logging.INFO, logger="app.email"):
        await provider.send(to="user@example.com", subject="Hi", body="secret-pass")
    assert "user@example.com" in caplog.text
    assert "secret-pass" in caplog.text
