from __future__ import annotations

from eval.codegen_smoke import smoke_test_skill
from eval.schema import EvalCase
from eval.verifier import verify_codegen_execution

_GOOD_CODE = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    out = os.path.join(output_dir, 'output.bin')\n"
    "    with open(input_path, 'rb') as src:\n"
    "        data = src.read()\n"
    "    with open(out, 'wb') as dst:\n"
    "        dst.write(data)\n"
    "    return {'produced': ['output.bin'], 'size': len(data)}\n"
)

# The exact class of bug memory clouddrive-codegen-smoke-test-dec documents:
# real-model-observed token-garbled typo, syntactically legal, undefined at
# runtime (os.path -> os.pathlext).
_BROKEN_CODE = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    out = os.pathlext.join(output_dir, 'output.bin')\n"
    "    return {}\n"
)

_NO_OUTPUT_CODE = "def run(input_path, output_dir, params):\n    return {'ok': True}\n"


def _case(**overrides: object) -> EvalCase:
    base: dict[str, object] = {"id": "t", "prompt": "p"}
    base.update(overrides)
    return EvalCase.model_validate(base)


def test_smoke_test_skill_passes_for_working_code_on_file() -> None:
    outcome = smoke_test_skill(code=_GOOD_CODE, item_types=["FILE"])
    assert outcome["ok"] is True
    assert outcome["results"]["FILE"]["ok"] is True
    assert outcome["results"]["FILE"]["produced_files"]


def test_smoke_test_skill_fails_for_broken_code() -> None:
    # AttributeError at runtime — codeguard's static AST scan wouldn't catch
    # this (os.pathlext is syntactically a valid attribute access).
    outcome = smoke_test_skill(code=_BROKEN_CODE, item_types=["FILE"])
    assert outcome["ok"] is False
    assert outcome["results"]["FILE"]["ok"] is False
    assert outcome["results"]["FILE"]["error"] is not None


def test_smoke_test_skill_fails_when_no_output_produced() -> None:
    outcome = smoke_test_skill(code=_NO_OUTPUT_CODE, item_types=["FILE"])
    assert outcome["ok"] is False
    assert outcome["results"]["FILE"]["produced_files"] == []


def test_smoke_test_skill_tries_both_declared_item_types() -> None:
    # _GOOD_CODE is FILE-only (opens input_path directly) — a skill declaring
    # FOLDER too must branch on os.path.isdir per codegen's own system prompt
    # (subagent.py). Confirms the smoke test genuinely exercises BOTH
    # declared types rather than stopping at the first: FILE passes, FOLDER
    # (correctly) fails for this FILE-only implementation.
    outcome = smoke_test_skill(code=_GOOD_CODE, item_types=["FILE", "FOLDER"])
    assert set(outcome["results"]) == {"FILE", "FOLDER"}
    assert outcome["results"]["FILE"]["ok"] is True
    assert outcome["results"]["FOLDER"]["ok"] is False
    assert outcome["ok"] is False  # declaring both means both must work


_DUAL_TYPE_CODE = (
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    out = os.path.join(output_dir, 'output.bin')\n"
    "    if os.path.isdir(input_path):\n"
    "        names = sorted(os.listdir(input_path))\n"
    "        data = ('\\n'.join(names)).encode()\n"
    "    else:\n"
    "        with open(input_path, 'rb') as src:\n"
    "            data = src.read()\n"
    "    with open(out, 'wb') as dst:\n"
    "        dst.write(data)\n"
    "    return {'produced': ['output.bin'], 'size': len(data)}\n"
)


def test_smoke_test_skill_passes_both_types_when_code_branches_correctly() -> None:
    outcome = smoke_test_skill(code=_DUAL_TYPE_CODE, item_types=["FILE", "FOLDER"])
    assert outcome["ok"] is True
    assert outcome["results"]["FILE"]["ok"] is True
    assert outcome["results"]["FOLDER"]["ok"] is True


def _m4_case() -> EvalCase:
    return _case(
        id="m4",
        expect={"workflow": {"skill_generated": "*"}},
    )


def test_verify_codegen_execution_no_op_for_non_m4_case() -> None:
    case = _case()  # no skill_generated declared
    response = {"skill_proposal": {"code": _GOOD_CODE, "manifest": {}}}
    assert verify_codegen_execution(case, response) == []


def test_verify_codegen_execution_fails_when_no_proposal() -> None:
    case = _m4_case()
    checks = verify_codegen_execution(case, {"skill_proposal": None})
    assert len(checks) == 1
    assert checks[0].ok is False


def test_verify_codegen_execution_runs_real_generated_code() -> None:
    case = _m4_case()
    response = {
        "skill_proposal": {
            "code": _GOOD_CODE,
            "manifest": {"ui": {"context_menu": [{"item_types": ["FILE"]}]}},
        }
    }
    checks = verify_codegen_execution(case, response)
    assert len(checks) == 1
    assert checks[0].dimension == "execution"
    assert checks[0].ok is True


def test_verify_codegen_execution_catches_broken_generated_code() -> None:
    case = _m4_case()
    response = {
        "skill_proposal": {
            "code": _BROKEN_CODE,
            "manifest": {"ui": {"context_menu": [{"item_types": ["FILE"]}]}},
        }
    }
    checks = verify_codegen_execution(case, response)
    assert checks[0].ok is False
