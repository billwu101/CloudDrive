from __future__ import annotations

from typing import Any

import pytest

from app.assistant.skills.manifest import validate_manifest
from app.core.exceptions import AppError


def _valid_manifest() -> dict[str, Any]:
    return {
        "name": "inspect_item_details",
        "description": "Show details for a selected drive item.",
        "version": "1.0.0",
        "ui": {
            "context_menu": [
                {
                    "label": "Inspect details",
                    "handler": "inspect_item_details",
                    "item_types": ["FILE", "FOLDER"],
                }
            ]
        },
    }


def test_valid_manifest_round_trips() -> None:
    manifest = validate_manifest(_valid_manifest())
    assert manifest.name == "inspect_item_details"
    assert manifest.ui.context_menu[0].handler == "inspect_item_details"
    assert manifest.ui.context_menu[0].item_types == ["FILE", "FOLDER"]


def test_manifest_defaults_empty_context_menu() -> None:
    manifest = validate_manifest({"name": "tidy_root", "description": "Tidy the root folder."})
    assert manifest.version == "1.0.0"
    assert manifest.ui.context_menu == []


def test_non_object_manifest_rejected() -> None:
    with pytest.raises(AppError, match="must be a JSON object"):
        validate_manifest(["not", "a", "dict"])


@pytest.mark.parametrize(
    "mutate",
    [
        lambda m: m.update(name="Bad Name"),  # spaces / uppercase
        lambda m: m.update(name="x"),  # too short
        lambda m: m.update(version="1.0"),  # not semver
        lambda m: m.update(description=""),  # empty
        lambda m: m.pop("name"),  # missing required
        lambda m: m["ui"]["context_menu"][0].update(item_types=[]),  # empty list
        lambda m: m["ui"]["context_menu"][0].update(item_types=["FILE", "FILE"]),  # dupes
        lambda m: m["ui"]["context_menu"][0].update(item_types=["DRIVE"]),  # bad enum
        lambda m: m["ui"]["context_menu"][0].update(extra="x"),  # extra field forbidden
    ],
)
def test_structurally_invalid_manifests_rejected(mutate: Any) -> None:
    manifest = _valid_manifest()
    mutate(manifest)
    with pytest.raises(AppError, match="Invalid skill manifest"):
        validate_manifest(manifest)


def test_context_menu_handler_must_match_skill_name() -> None:
    manifest = _valid_manifest()
    manifest["ui"]["context_menu"][0]["handler"] = "some_other_skill"
    with pytest.raises(AppError, match="does not match skill name"):
        validate_manifest(manifest)
