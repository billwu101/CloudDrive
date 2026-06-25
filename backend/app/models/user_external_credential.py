from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserExternalCredential(Base):
    """A user's encrypted credential for an external model provider (DEC-026).

    One row per (user, provider). The secret (API key or OAuth token JSON) is
    stored encrypted at rest; only ``masked_hint`` is ever returned to clients.
    """

    __tablename__ = "user_external_credentials"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    # "openai" (API key) | "codex" (subscription OAuth token)
    provider: Mapped[str] = mapped_column(String(20), primary_key=True)
    # "api_key" | "oauth_token"
    auth_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Fernet-encrypted secret; never returned in plaintext.
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # e.g. "sk-…abcd" — last 4 chars only, safe to show.
    masked_hint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # "active" | "invalid" (set when a call rejects the credential)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
