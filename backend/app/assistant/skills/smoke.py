"""Run a freshly generated skill once before showing it to the user.

``author()`` validates generated code statically (AST safety scan + manifest
schema) and never executes it, so a skill can look perfect and still die on its
first real run. Measured on the 2026-07-29 full eval: **18 of 100** generated
skills raised on the very first call — token-garbled identifiers
(``outputode_dir``, ``files_to``), a regex with a bad escape, a ``str`` used as
a ``Path``. All syntactically legal; all invisible to a static scan.

The user only ever sees these after approving and installing the skill, which
is the wrong end of the process to discover them. So: run the code once on a
throwaway fixture, and when it dies of something that is clearly a *code*
defect, hand the traceback back to the model as a repair problem — the same
loop that already fixes manifest errors.

**Only code defects trigger a repair.** A skill written for PNGs, handed a text
fixture, will fail — and "fix" attempts against a phantom input problem made
things worse when the eval harness made this exact mistake (48 of 99 M4
failures turned out to be fixture mismatch, not model error). Anything that
looks like the input being the wrong shape is reported as "unchecked", never as
a defect.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from app.assistant.skills.sandbox import SandboxResult, SkillSandbox

# Exception types that mean "this code is broken", as opposed to "this input is
# not what the code expects". Anchored on the failures actually observed.
_CODE_DEFECT_MARKERS = (
    "NameError",
    "SyntaxError",
    "IndentationError",
    "AttributeError",
    "UnboundLocalError",
    "TypeError",
    "re.error",
    "bad escape",
    "ModuleNotFoundError",
    "ImportError",
)
_FIXTURE_TEXT = "smoke test\nline two\n"


@dataclass(frozen=True)
class SmokeOutcome:
    """``ok``: the code ran. ``is_code_defect``: and if not, is it the code's
    fault? Only then is ``error`` worth sending back to the model."""

    ok: bool
    error: str = ""
    is_code_defect: bool = False


def _looks_like_code_defect(error: str) -> bool:
    return any(marker in error for marker in _CODE_DEFECT_MARKERS)


def _fixture(item_type: str, root: Path) -> Path:
    """A minimal input of the declared kind. Deliberately plain text: guessing
    a format from the skill's name is how the eval harness ended up testing its
    own fixtures instead of the model (see module docstring)."""

    if item_type == "FOLDER":
        folder = root / "input"
        (folder / "sub").mkdir(parents=True)
        (folder / "a.txt").write_text(_FIXTURE_TEXT, encoding="utf-8")
        (folder / "sub" / "b.txt").write_text(_FIXTURE_TEXT, encoding="utf-8")
        return folder
    path = root / "sample.txt"
    path.write_text(_FIXTURE_TEXT, encoding="utf-8")
    return path


def smoke_test_generated_code(
    sandbox: SkillSandbox, code: str, item_types: list[str]
) -> SmokeOutcome:
    """Run ``code`` once per declared item type against a throwaway fixture.

    Returns on the first code defect found. A run that fails for any other
    reason — or produces no file — counts as ok here: this checks that the code
    is *runnable*, not that it did the right thing with an input it was never
    designed for.
    """

    for item_type in item_types or ["FILE"]:
        root = Path(tempfile.mkdtemp(prefix="skill_smoke_"))
        try:
            result: SandboxResult = sandbox.run(
                code=code,
                input_path=_fixture(item_type, root),
                params={"filename": "sample.txt", "item_type": item_type},
            )
            if not result.ok:
                error = result.error or "unknown error"
                if _looks_like_code_defect(error):
                    return SmokeOutcome(
                        ok=False,
                        error=f"running it on a {item_type} input raised: {error}",
                        is_code_defect=True,
                    )
        finally:
            sandbox.cleanup()
            shutil.rmtree(root, ignore_errors=True)
    return SmokeOutcome(ok=True)
