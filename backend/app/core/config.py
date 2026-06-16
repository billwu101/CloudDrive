from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/clouddrive"
    jwt_secret_key: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]
    storage_driver: str = "local"
    local_storage_path: str = "/tmp/cloud-drive-storage"
    max_upload_size_bytes: int = 100 * 1024 * 1024  # 100 MB
    default_user_quota_bytes: int = 15 * 1024 * 1024 * 1024  # 15 GB

    # Email / password-reset delivery
    email_provider: str = "console"  # "console" (log only) | "smtp"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = "Cloud Drive <no-reply@clouddrive.local>"
    smtp_use_tls: bool = True  # STARTTLS

    # In-app AI assistant
    assistant_enabled: bool = True
    llm_provider: str = "ollama"
    llm_base_url: str = "http://localhost:11434"
    assistant_model: str = "gemma-4-26b"
    llm_num_ctx: int = 8192
    assistant_max_tool_iterations: int = 8
    assistant_sandbox_timeout_sec: int = 30

    # Optional external model fallback. Disabled by default; privacy gates apply first.
    external_llm_enabled: bool = False
    max_local_attempts: int = 3
    external_llm_base_url: str = ""
    external_model: str = ""
    external_llm_api_key: str = ""
    privacy_default: str = "sensitive"


@lru_cache
def get_settings() -> Settings:
    return Settings()
