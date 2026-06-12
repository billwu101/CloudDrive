import pytest

from app.core.config import Settings, get_settings


def test_settings_load_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/mydb")
    monkeypatch.setenv("JWT_SECRET_KEY", "supersecret")
    monkeypatch.setenv("CORS_ORIGINS", '["https://example.com"]')

    settings = Settings()
    assert settings.database_url == "postgresql+asyncpg://u:p@localhost/mydb"
    assert settings.jwt_secret_key == "supersecret"
    assert settings.cors_origins == ["https://example.com"]


def test_settings_defaults() -> None:
    settings = Settings()
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes == 30
    assert settings.refresh_token_expire_days == 30
    assert settings.storage_driver == "local"


def test_get_settings_returns_cached_instance() -> None:
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
