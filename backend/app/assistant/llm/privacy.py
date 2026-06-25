from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

PrivacyDefault = Literal["sensitive", "non_sensitive"]

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)


@dataclass(frozen=True)
class PrivacyDecision:
    is_sensitive: bool
    text_for_external: str
    deidentified: bool
    reason: str


def classify_and_deidentify(text: str, *, default: PrivacyDefault) -> PrivacyDecision:
    if default == "sensitive":
        return PrivacyDecision(
            is_sensitive=True,
            text_for_external=text,
            deidentified=False,
            reason="privacy default is sensitive",
        )

    redacted = _UUID_RE.sub("[uuid]", _EMAIL_RE.sub("[email]", text))
    return PrivacyDecision(
        is_sensitive=redacted != text,
        text_for_external=redacted,
        deidentified=redacted != text,
        reason="detected identifiers" if redacted != text else "no sensitive markers detected",
    )
