"""Browser mode must seed everything API mode seeds.

Twice now a new seeding mechanism landed in `eval/runner.py` without reaching
`eval/runner_browser.py` (`seed_folders`, 2026-07-27; `seed_files`, found by
the 2026-07-28 audit), leaving `mode: [api, browser]` cases running against an
empty drive in browser mode — failures that say nothing about the model. This
pins the parity.
"""

from __future__ import annotations

from eval.runner_browser import build_payload
from eval.schema import EvalCase


def _case(**overrides: object) -> EvalCase:
    base: dict[str, object] = {"id": "t", "prompt": "p"}
    base.update(overrides)
    return EvalCase.model_validate(base)


def test_payload_carries_seed_files() -> None:
    case = _case(seed_files=["sample.pdf", "sample.png"])
    assert build_payload([case])[0]["seed_files"] == [
        {"fixture": "sample.pdf", "name": "sample.pdf"},
        {"fixture": "sample.png", "name": "sample.png"},
    ]


def test_payload_carries_renamed_seed_files() -> None:
    """The filename-classification cases upload one fixture many times under
    meaningful names. Left as SeedFile objects, the payload could not even be
    serialised — json.dumps raised before Playwright started (2026-07-29, the
    first time browser mode was actually run)."""

    case = _case(
        seed_files=[
            {"fixture": "sample.pdf", "name": "發票A.pdf"},
            {"fixture": "sample.pdf", "name": "考卷B.pdf"},
        ]
    )

    payload = build_payload([case])[0]["seed_files"]

    assert payload == [
        {"fixture": "sample.pdf", "name": "發票A.pdf"},
        {"fixture": "sample.pdf", "name": "考卷B.pdf"},
    ]
    import json

    json.dumps(payload)  # the actual failure mode: not serialisable


def test_payload_carries_seed_folders() -> None:
    case = _case(seed_folders=["報告"])
    assert build_payload([case])[0]["seed_folders"] == ["報告"]


def test_payload_omits_empty_seed_fields() -> None:
    item = build_payload([_case()])[0]
    assert "seed_files" not in item
    assert "seed_folders" not in item


def test_generated_cases_needing_fixtures_are_seedable_in_browser_mode() -> None:
    # The concrete regression: organize_by_type cases declare browser mode and
    # need real files on the drive to have anything to classify.
    case = _case(
        id="gen-ec2-093",
        mode=["api", "browser"],
        seed_files=["sample.pdf", "sample.png"],
        expect={"state": {"item_parent": {"sample.pdf": "pdf-files"}}},
    )
    assert build_payload([case])[0]["seed_files"]
