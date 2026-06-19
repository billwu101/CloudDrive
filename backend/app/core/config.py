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
    llm_base_url: str = "http://192.168.10.75:11434"
    llm_api_key: str = "ollama-local"
    assistant_model: str = "gemma4:26b"
    llm_num_ctx: int = 65536
    llm_timeout_seconds: float = 300
    llm_keep_alive: str = "15m"
    assistant_max_tool_iterations: int = 8
    assistant_sandbox_timeout_sec: int = 30

    # Optional external model fallback. Disabled by default; privacy gates apply first.
    external_llm_enabled: bool = False
    max_local_attempts: int = 3
    external_llm_base_url: str = ""
    external_model: str = ""
    external_llm_api_key: str = ""
    privacy_default: str = "sensitive"

    # Per-user external model credentials (DEC-026). CREDENTIAL_ENCRYPTION_KEY is a
    # urlsafe-base64 Fernet key (generate: Fernet.generate_key()); empty disables
    # per-user credentials. Path B (OpenAI API key) calls external_api_base_url
    # with external_chat_model.
    credential_encryption_key: str = ""
    external_api_base_url: str = "https://api.openai.com/v1"
    external_chat_model: str = "gpt-5.5"

    # Time Machine background scheduler (in-process loop). Off by default — enable
    # in a single-worker deployment, or run an external cron calling the same
    # SnapshotService methods for multi-worker setups.
    snapshot_scheduler_enabled: bool = False
    snapshot_scheduler_tick_seconds: int = 300  # how often the loop wakes up
    snapshot_gc_interval_minutes: int = 360  # how often to run blob GC
    snapshot_gc_grace_minutes: int = 60  # protect blobs newer than this from GC

    # Semantic search (embeddings via Ollama + pgvector). Off by default so
    # uploads don't block on an embedding model that may not be installed.
    embedding_enabled: bool = False
    embedding_model: str = "nomic-embed-text"
    embedding_base_url: str = ""  # falls back to llm_base_url when empty
    # Must match the model's output dimension AND the vector() column width in
    # migration 0012 (default nomic-embed-text = 768).
    embedding_dim: int = 768


@lru_cache
def get_settings() -> Settings:
    return Settings()
