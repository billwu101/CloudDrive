import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from cryptography.fernet import Fernet

_FALLBACK_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/clouddrive_test"


def _default_database_url() -> str:
    """Test database URL, derived from the dev one in ``.env`` when there is one.

    Only the database name is swapped (``clouddrive`` -> ``clouddrive_test``);
    host, port and credentials are whatever the developer already runs. A dev
    Postgres on a non-default port (this project uses 5434) otherwise left every
    integration test erroring with "Connect call failed ('127.0.0.1', 5432)",
    which reads like a broken suite instead of a URL pointing at nothing.

    Parsed by hand rather than via ``get_settings()``: this file must set the
    environment BEFORE anything imports the app, and importing the app here
    would cache settings from the very environment we are still assembling.
    """

    env_file = Path(__file__).resolve().parents[1] / ".env"
    if not env_file.is_file():
        return _FALLBACK_DB_URL
    for line in env_file.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry.startswith("DATABASE_URL="):
            continue
        parsed = urlsplit(entry.split("=", 1)[1].strip())
        if parsed.hostname:
            return urlunsplit(parsed._replace(path="/clouddrive_test"))
    return _FALLBACK_DB_URL


# Set required env vars before any app imports so get_settings() caches correct values.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", _default_database_url())
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("JWT_ALGORITHM", "HS256")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')
# Share links keep a recoverable copy of their token under this key (design
# §6.12.11 rule 3a). A fixed test key keeps encrypt/decrypt exercised rather
# than silently skipped.
os.environ.setdefault("CREDENTIAL_ENCRYPTION_KEY", Fernet.generate_key().decode())
