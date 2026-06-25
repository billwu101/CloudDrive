from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExternalCredentialUpsert(BaseModel):
    provider: Literal["openai", "codex"]
    auth_type: Literal["api_key", "oauth_token"]
    # The plaintext API key (openai) or OAuth token JSON (codex). Stored encrypted;
    # never returned. Required, non-empty.
    secret: str = Field(min_length=1)


class ExternalCredentialView(BaseModel):
    """What clients see — masked, never the secret."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    auth_type: str
    masked_hint: str
    status: str
    updated_at: datetime
