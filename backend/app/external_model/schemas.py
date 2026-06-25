from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# Protocol/source of a connection. "openai_compatible" covers OpenAI, Gemini,
# Groq, etc. (anything exposing /chat/completions); "ollama" for Ollama cloud or
# self-hosted; "codex" for a ChatGPT-subscription OAuth token via the codex CLI.
ConnectionKind = Literal["openai_compatible", "ollama", "codex"]


class ConnectionCreate(BaseModel):
    label: str = Field(min_length=1, max_length=100)
    kind: ConnectionKind
    base_url: str = Field(default="", max_length=500)
    model: str = Field(default="", max_length=200)
    # Plaintext API key (openai_compatible/ollama) or auth.json (codex). Stored
    # encrypted; never returned. Required, non-empty.
    secret: str = Field(min_length=1)


class ConnectionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)
    base_url: str | None = Field(default=None, max_length=500)
    model: str | None = Field(default=None, max_length=200)
    # New secret; omit to keep the existing one.
    secret: str | None = Field(default=None, min_length=1)


class ConnectionView(BaseModel):
    """What clients see — masked, never the secret."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    label: str
    kind: str
    base_url: str
    model: str
    masked_hint: str
    status: str
    updated_at: datetime
