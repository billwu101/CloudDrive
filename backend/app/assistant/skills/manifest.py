"""Skill manifest schema and validation.

A manifest is the user-approvable, declarative surface of an assistant skill:
its identity (``name``/``description``/``version``) and how it surfaces in the
UI (``ui.context_menu``). Generated or hand-authored manifests must pass
``validate_manifest`` before they are persisted as a pending proposal or
installed — a malformed manifest can never reach the right-click menu.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError

ItemType = Literal["FILE", "FOLDER"]

# Skill names double as registry keys and context-menu handlers, so keep them
# to a strict identifier shape (lowercase, digits, underscores).
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ContextMenuAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=64)
    handler: str = Field(min_length=2, max_length=64)
    item_types: list[ItemType] = Field(min_length=1)

    @field_validator("handler")
    @classmethod
    def _handler_is_identifier(cls, value: str) -> str:
        if not _NAME_RE.match(value):
            raise ValueError(f"handler must be a skill identifier: {value!r}")
        return value

    @field_validator("item_types")
    @classmethod
    def _item_types_unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("item_types must not contain duplicates")
        return value


class SkillManifestUI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    context_menu: list[ContextMenuAction] = Field(default_factory=list)


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=64)
    description: str = Field(min_length=1, max_length=500)
    version: str = "1.0.0"
    ui: SkillManifestUI = Field(default_factory=SkillManifestUI)

    @field_validator("name")
    @classmethod
    def _name_is_identifier(cls, value: str) -> str:
        if not _NAME_RE.match(value):
            raise ValueError(f"name must be a skill identifier: {value!r}")
        return value

    @field_validator("version")
    @classmethod
    def _version_is_semver(cls, value: str) -> str:
        if not _VERSION_RE.match(value):
            raise ValueError(f"version must be MAJOR.MINOR.PATCH: {value!r}")
        return value


def validate_manifest(raw: Any) -> SkillManifest:
    """Validate a raw manifest dict, raising ``AppError`` on any problem.

    Beyond the structural schema, this enforces that every ``context_menu``
    handler references the manifest's own skill ``name`` — a menu entry can
    only ever invoke the skill it ships with.
    """

    if not isinstance(raw, dict):
        raise AppError(ErrorCode.INVALID_OPERATION, "Manifest must be a JSON object")
    try:
        manifest = SkillManifest.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first.get("loc", ())) or "manifest"
        raise AppError(
            ErrorCode.INVALID_OPERATION,
            f"Invalid skill manifest at {location}: {first.get('msg', 'invalid')}",
        ) from exc

    for action in manifest.ui.context_menu:
        if action.handler != manifest.name:
            raise AppError(
                ErrorCode.INVALID_OPERATION,
                (
                    f"Context-menu handler {action.handler!r} does not match "
                    f"skill name {manifest.name!r}"
                ),
            )
    return manifest
