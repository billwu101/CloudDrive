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

    # Chunked resumable upload (proposal §27.7)
    upload_chunk_size_bytes: int = 8 * 1024 * 1024  # 8 MB per chunk
    max_chunked_upload_size_bytes: int = 5 * 1024 * 1024 * 1024  # 5 GB per file
    upload_session_retention_days: int = 7  # unfinished sessions are reclaimed
    # Files at or below this go through /upload/simple; larger ones use a
    # chunked session. Kept at the simple-upload cap so the two paths meet.
    chunked_upload_threshold_bytes: int = 100 * 1024 * 1024
    # Periodic reclaim of expired sessions. Single-process only: with several
    # workers, disable this and drive cleanup_expired from an external cron.
    upload_cleanup_scheduler_enabled: bool = False
    upload_cleanup_interval_hours: int = 24

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
    # "ollama" → local Ollama (/api/chat); "openai_compatible" → an endpoint
    # exposing OpenAI /v1/chat/completions (uses ExternalLLMClient as the local
    # executor). llm_base_url/assistant_model/llm_api_key apply to both.
    llm_provider: str = "ollama"
    llm_base_url: str = "http://192.168.10.75:11434"
    # Optional fallback Ollama endpoint; tried when llm_base_url is unreachable.
    llm_fallback_base_url: str = ""
    llm_api_key: str = "ollama-local"
    assistant_model: str = "gemma4:26b"
    llm_num_ctx: int = 65536
    llm_timeout_seconds: float = 300
    llm_keep_alive: str = "15m"
    # Anti-loop guards for the local model (DEC-031): cap generated tokens so a
    # degenerate repetition loop fails bounded instead of eating the full read
    # timeout (0 = uncapped), and use a small non-zero temperature for
    # structured requests so greedy decoding cannot lock into a repetition
    # cycle — the output format is guaranteed by the grammar, not temperature.
    llm_num_predict: int = 2048
    llm_structured_temperature: float = 0.2
    # Codegen needs full sampling: at 0.2 the model produced broken code
    # (baseline at Ollama's default 0.8 authored valid skills 2/2 — see
    # proposal-planner-skill-enum §7). Overrides the structured pin per call.
    llm_codegen_temperature: float = 0.8
    # E8 experiment knob: send Ollama `think: false` on every local request.
    # Loops live in the thinking phase; this measures whether disabling it
    # cures them without hurting plan quality. Off by default. This is the
    # client-wide constructor default; a per-call value (below) wins over it.
    llm_disable_thinking: bool = False
    # DEC-033: the planner runs with thinking disabled by default. E8 (60 samples,
    # real model) showed think:false cured all repetition loops and cut planner
    # latency ~10x with no measurable loss in plan quality on gemma4:26b. Set False
    # to restore planner thinking (e.g. after swapping in a stronger thinking model;
    # re-run the E8 A/B before flipping).
    llm_planner_disable_thinking: bool = True
    # Codegen: 2026-07-22 A/B on real gemma4:26b — thinking-on codegen falls into
    # repetition loops (per-call 0/6; M4 skill-generation 0% → 100% with think:false).
    # Supersedes the earlier "codegen validated with thinking on" assumption.
    llm_codegen_disable_thinking: bool = True
    # 2026-07-29 experiment: two-phase planning. When the planner cannot know
    # which items to act on until it has seen a query's result, it plans only
    # the read steps and sets needs_followup; the service executes those, feeds
    # the real results back, and the second pass appends its steps to the SAME
    # plan (so step references, the confirm gate and the executor are unchanged).
    # Off by default — the 425-case eval baseline was measured without it.
    assistant_two_phase_planning: bool = False
    assistant_max_tool_iterations: int = 8
    assistant_sandbox_timeout_sec: int = 30
    # DEC-035: caps on materializing a folder subtree into the sandbox input when a
    # generated skill runs on a FOLDER. Guards against a huge folder blowing up the
    # temp dir / sandbox. Exceeding either raises before any download happens.
    assistant_folder_max_files: int = 1000
    assistant_folder_max_bytes: int = 500 * 1024 * 1024
    # Conversation memory: how many of the most recent stored messages (user +
    # assistant) are replayed into the planner as context so follow-ups can
    # resolve references ("rename the first one"). 0 disables memory (single-turn).
    # ContextManager.trim still enforces the hard num_ctx budget on top of this.
    assistant_history_max_messages: int = 12

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
    # Path A (Codex subscription): the official `codex` CLI binary used to bridge
    # a user's subscription (EM3). Must be installed in the runtime image.
    codex_bin: str = "codex"

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
