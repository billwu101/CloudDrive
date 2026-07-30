"""The reset endpoint answers identically whether or not mail was sent — by
design. These tests cover the only place that difference can surface."""

from __future__ import annotations

import logging

from app.core.config import Settings
from app.email.diagnostics import check_mail_on_startup, describe_delivery


def _settings(**overrides: object) -> Settings:
    return Settings(_env_file=None, **overrides)  # type: ignore[arg-type]


def test_smtp_with_a_host_delivers() -> None:
    d = describe_delivery(_settings(email_provider="smtp", smtp_host="smtp.example.com"))
    assert d.delivers is True
    assert d.effective == "smtp"
    assert d.reason is None


def test_console_provider_does_not_deliver() -> None:
    d = describe_delivery(_settings())
    assert d.delivers is False
    assert d.effective == "console"
    assert "not 'smtp'" in (d.reason or "")


def test_smtp_without_a_host_silently_becomes_console() -> None:
    # The factory falls back rather than crashing, which is the whole reason
    # this needs reporting: the config says smtp and nothing is sent.
    d = describe_delivery(_settings(email_provider="smtp", smtp_host=""))
    assert d.delivers is False
    assert d.effective == "console"
    assert "SMTP_HOST is empty" in (d.reason or "")


def test_production_without_delivery_logs_an_error(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.WARNING, logger="app.email"):
        check_mail_on_startup(_settings(app_env="production"))

    record = next(r for r in caplog.records if r.name == "app.email")
    assert record.levelno == logging.ERROR
    assert "NOT DELIVERING" in record.getMessage()
    # The consequence, not just the state — someone reading logs at 2am should
    # not have to infer what a console mailer means.
    assert "silently broken" in record.getMessage()


def test_development_without_delivery_only_warns(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.WARNING, logger="app.email"):
        check_mail_on_startup(_settings(app_env="development"))

    record = next(r for r in caplog.records if r.name == "app.email")
    assert record.levelno == logging.WARNING


def test_configured_delivery_is_reported_at_info(caplog) -> None:  # type: ignore[no-untyped-def]
    with caplog.at_level(logging.INFO, logger="app.email"):
        check_mail_on_startup(
            _settings(app_env="production", email_provider="smtp", smtp_host="smtp.example.com")
        )

    record = next(r for r in caplog.records if r.name == "app.email")
    assert record.levelno == logging.INFO
    assert "smtp.example.com" in record.getMessage()
