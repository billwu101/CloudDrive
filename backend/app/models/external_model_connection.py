from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ExternalModelConnection(Base):
    """A user's named connection to an external model source.

    Supersedes the single-credential-per-provider model: a user may store many
    connections, each with its own ``label``, ``kind`` (protocol), ``base_url``,
    ``model`` and encrypted secret — so they can switch keys/models freely. The
    secret (API key or Codex auth.json) is stored encrypted; only ``masked_hint``
    is ever returned to clients.
    """

    __tablename__ = "external_model_connections"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # User-chosen display name, e.g. "My Gemini", "Ollama free".
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    # Protocol/source: "openai_compatible" (OpenAI, Gemini, Groq, …) | "ollama" | "codex".
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    # Endpoint for openai_compatible / ollama; unused for codex.
    base_url: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    # Model id for this connection, e.g. "gemini-2.5-flash-lite".
    model: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # Fernet-encrypted secret (API key, or codex auth.json); never returned.
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    masked_hint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # "active" | "invalid" (set when a call rejects the credential).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
