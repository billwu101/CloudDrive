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
is JSON-serialisable. It does NOT check the output's semantic correctness
(e.g. that an md5_checksum skill's hash is actually correct) — that would
need a reference implementation per skill type, out of scope here.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.assistant.skills.sandbox import SkillSandbox

_FILE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "sample.txt"


def _folder_fixture() -> Path:
    """Minimal FOLDER input: 1-2 files + a subfolder, per the smoke-test spec
    in memory clouddrive-codegen-smoke-test-dec. Caller must delete it."""
    root = Path(tempfile.mkdtemp(prefix="codegen_smoke_folder_"))
    (root / "a.txt").write_text("hello\n", encoding="utf-8")
    sub = root / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("world\n", encoding="utf-8")
    return root


def smoke_test_skill(*, code: str, item_types: list[str], timeout_sec: int = 20) -> dict[str, Any]:
    """Run ``code`` against a minimal fixture for each declared item_type.

    Returns ``{"ok": bool, "results": {item_type: {ok, error, produced_files,
    json_serializable}}}``. ``ok`` is True only if every declared item_type
    ran cleanly (a skill declaring both FILE and FOLDER must handle both —
    per the memory spec, "FILE+FOLDER 兩種都要試,不能只測一種").
    """
    types = item_types or ["FILE"]
    results: dict[str, Any] = {}
    all_ok = True
    for item_type in types:
        folder_fixture: Path | None = None
        if item_type == "FILE":
            fixture = _FILE_FIXTURE
        else:
            folder_fixture = _folder_fixture()
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
            ok = outcome.ok and len(produced) >= 1 and json_serializable
            results[item_type] = {
                "ok": ok,
                "error": outcome.error,
                "produced_files": produced,
                "json_serializable": json_serializable,
            }
            all_ok = all_ok and ok
        finally:
            sandbox.cleanup()
            if folder_fixture is not None:
                shutil.rmtree(folder_fixture, ignore_errors=True)
    return {"ok": all_ok, "results": results}
