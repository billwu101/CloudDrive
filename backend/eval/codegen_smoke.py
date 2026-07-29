"""M4 smoke-test: does a generated skill's code actually run? (2026-07-28, alfred)

``CodegenSubAgent.author()`` only statically validates generated code (AST
safety scan + manifest schema) — it never executes it. A skill can pass those
checks and still crash on first real run (real-model-observed symptom:
token-garbled typos like ``os.pathlext`` that are syntactically legal but
undefined). "M4 只驗證有沒有提出技能提案...功能不對、程式碼的結果不對，
做錯了根本就沒有意義" (alfred).

This runs the REAL generated code (not a hand-written reference — unlike
``eval/exec_runner.py``, which runs a case author's known-good ``code`` for a
handful of hand-written exec cases) in the same ``SkillSandbox`` production
uses, against a minimal generic fixture matched to the skill's declared
``item_types``.

Deliberately scoped as a SMOKE test, not full correctness verification per
skill type — 100 different generated skills, no hand-written expected output
per type. This is the already-agreed scope from
memory clouddrive-codegen-smoke-test-dec (alfred, 2026-07-24, deferred at the
time to "another DEC, don't merge into the folder-skill PR"): run() is
callable without error, output_dir gets at least one file, the return value
is JSON-serialisable.

2026-07-29: extended one tier further, to what the output *is* — see
``eval/output_checks.py``. Non-empty, parseable as whatever its extension
claims, and (for hash skills) carrying the input's real digest. Full per-skill
correctness still needs a reference implementation per skill type and remains
out of scope; these three need no expected value, so they cost nothing to add
and catch the "ran fine, wrote garbage" class the file-exists check waved
through.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.assistant.skills.sandbox import SkillSandbox
from eval.output_checks import OutputReport, check_outputs

_FILE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.txt"


def _resolve_fixture(name: str | None) -> Path:
    """The input a generated skill is smoke-tested against.

    ``None`` keeps the historical plain-text fixture (right for hash / encode /
    compress / text-processing skills). A named fixture is required for skills
    whose input must be a specific format — feeding sample.txt to an image or
    PDF skill tests the fixture, not the model (2026-07-28: that alone accounted
    for 48 of 99 M4 failures)."""

    if name is None:
        return _FILE_FIXTURE
    path = _FILE_FIXTURE.parent / name
    if not path.is_file():
        raise FileNotFoundError(f"codegen_fixture not found: {path}")
    return path


def _folder_fixture(source: Path) -> Path:
    """Minimal FOLDER input: two copies of the skill's own file fixture, one of
    them nested (per the smoke-test spec in memory
    clouddrive-codegen-smoke-test-dec). Caller must delete it.

    2026-07-28 second pass: this used to always create a.txt + sub/b.txt, so a
    skill declaring [FILE, FOLDER] got a matching file for its FILE run and a
    folder of plain text for its FOLDER run — the same fixture mismatch that
    invalidated the FILE results, one level down (10 of the 29 remaining M4
    failures were FOLDER-only). Building the folder from ``source`` keeps both
    item types on inputs the skill can actually work on."""

    root = Path(tempfile.mkdtemp(prefix="codegen_smoke_folder_"))
    shutil.copy(source, root / source.name)
    sub = root / "sub"
    sub.mkdir()
    shutil.copy(source, sub / source.name)
    return root


def smoke_test_skill(
    *,
    code: str,
    item_types: list[str],
    timeout_sec: int = 20,
    file_fixture: str | None = None,
) -> dict[str, Any]:
    """Run ``code`` against a minimal fixture for each declared item_type.

    Returns ``{"ok": bool, "results": {item_type: {ok, error, produced_files,
    json_serializable, output_problems}}}``. ``ok`` is True only if every declared item_type
    ran cleanly (a skill declaring both FILE and FOLDER must handle both —
    per the memory spec, "FILE+FOLDER 兩種都要試,不能只測一種").
    """
    types = item_types or ["FILE"]
    results: dict[str, Any] = {}
    all_ok = True
    for item_type in types:
        folder_fixture: Path | None = None
        resolved = _resolve_fixture(file_fixture)
        if item_type == "FILE":
            fixture = resolved
        else:
            folder_fixture = _folder_fixture(resolved)
            fixture = folder_fixture
        sandbox = SkillSandbox(timeout_sec=timeout_sec)
        try:
            outcome = sandbox.run(code=code, input_path=fixture, params={"item_type": item_type})
            json_serializable = True
            if outcome.ok:
                try:
                    json.dumps(outcome.output)
                except (TypeError, ValueError):
                    json_serializable = False
            produced = outcome.produced_files
            # Beyond "a file exists": is what it wrote usable? Non-empty, and
            # parseable as whatever its extension claims, and — for the hash
            # skills the model generates most often — actually the input's
            # digest. See eval/output_checks.py for why these three and not more.
            output_dir = sandbox.last_output_dir
            content: OutputReport = (
                check_outputs(output_dir, fixture)
                if outcome.ok and produced and output_dir is not None
                else {"ok": True, "problems": [], "checked_files": 0}
            )
            ok = outcome.ok and len(produced) >= 1 and json_serializable and content["ok"]
            results[item_type] = {
                "ok": ok,
                "error": outcome.error,
                "produced_files": produced,
                "json_serializable": json_serializable,
                "output_problems": content["problems"],
            }
            all_ok = all_ok and ok
        finally:
            sandbox.cleanup()
            if folder_fixture is not None:
                shutil.rmtree(folder_fixture, ignore_errors=True)
    return {"ok": all_ok, "results": results}
