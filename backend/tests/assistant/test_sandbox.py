from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

from app.assistant.skills.codeguard import validate_skill_code
from app.assistant.skills.sandbox import SkillSandbox

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="sandbox relies on POSIX process groups / setrlimit"
)


def _input_file(tmp_path: Path, content: bytes = b"hello") -> Path:
    p = tmp_path / "input.bin"
    p.write_bytes(content)
    return p


# ── SkillSandbox (runtime containment) ────────────────────────────────────────


def test_benign_code_runs_and_writes_to_output(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        import os
        def run(input_path, output_dir, params):
            with open(input_path, "rb") as f:
                data = f.read()
            out = os.path.join(output_dir, "copy.txt")
            with open(out, "w") as f:
                f.write("len=" + str(len(data)))
            return {"bytes": len(data), "name": params.get("name")}
        """
    )
    sandbox = SkillSandbox(timeout_sec=10)
    result = sandbox.run(code=code, input_path=_input_file(tmp_path), params={"name": "x"})

    assert result.ok is True, result.error
    assert result.output == {"bytes": 5, "name": "x"}
    assert "copy.txt" in result.produced_files
    assert sandbox.last_output_dir is not None
    assert (sandbox.last_output_dir / "copy.txt").read_text() == "len=5"
    sandbox.cleanup()


def test_infinite_loop_times_out(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        def run(input_path, output_dir, params):
            while True:
                pass
        """
    )
    sandbox = SkillSandbox(timeout_sec=2)
    result = sandbox.run(code=code, input_path=_input_file(tmp_path))

    assert result.ok is False
    assert result.timed_out is True
    sandbox.cleanup()


def test_network_access_is_blocked(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        import socket
        def run(input_path, output_dir, params):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(("93.184.216.34", 80))
            return {"connected": True}
        """
    )
    sandbox = SkillSandbox(timeout_sec=10)
    result = sandbox.run(code=code, input_path=_input_file(tmp_path))

    assert result.ok is False
    assert "network" in (result.error or "").lower()
    sandbox.cleanup()


def test_write_outside_output_is_blocked(tmp_path: Path) -> None:
    escape_target = tmp_path / "escape.txt"
    code = textwrap.dedent(
        f"""
        def run(input_path, output_dir, params):
            with open({str(escape_target)!r}, "w") as f:
                f.write("pwned")
            return {{"ok": True}}
        """
    )
    sandbox = SkillSandbox(timeout_sec=10)
    result = sandbox.run(code=code, input_path=_input_file(tmp_path))

    assert result.ok is False
    assert "sandbox" in (result.error or "").lower()
    assert not escape_target.exists()
    sandbox.cleanup()


def test_subprocess_spawn_is_blocked(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        import subprocess
        def run(input_path, output_dir, params):
            subprocess.run(["echo", "hi"])
            return {"ran": True}
        """
    )
    sandbox = SkillSandbox(timeout_sec=10)
    result = sandbox.run(code=code, input_path=_input_file(tmp_path))

    assert result.ok is False
    assert (
        "process execution is blocked" in (result.error or "").lower()
        or "blocked" in (result.error or "").lower()
    )
    sandbox.cleanup()


def test_missing_run_entrypoint_reports_error(tmp_path: Path) -> None:
    sandbox = SkillSandbox(timeout_sec=10)
    result = sandbox.run(code="x = 1\n", input_path=_input_file(tmp_path))

    assert result.ok is False
    assert "run(" in (result.error or "")
    sandbox.cleanup()


# ── codeguard (static validation) ─────────────────────────────────────────────


def test_codeguard_accepts_clean_code() -> None:
    code = textwrap.dedent(
        """
        import zipfile
        import os
        def run(input_path, output_dir, params):
            with zipfile.ZipFile(input_path) as z:
                z.extractall(output_dir)
            return {"files": os.listdir(output_dir)}
        """
    )
    assert validate_skill_code(code) == []


@pytest.mark.parametrize(
    ("code", "needle"),
    [
        ("def run(a, b, c):\n    return {}\n", "input_path, output_dir, params"),
        ("x = 1\n", "missing required entrypoint"),
        (
            "import subprocess\ndef run(input_path, output_dir, params):\n    return {}\n",
            "forbidden import: subprocess",
        ),
        (
            "import socket\ndef run(input_path, output_dir, params):\n    return {}\n",
            "forbidden import: socket",
        ),
        (
            "def run(input_path, output_dir, params):\n    return eval('1')\n",
            "forbidden use of 'eval'",
        ),
        (
            "import os\ndef run(input_path, output_dir, params):\n    os.system('rm -rf /')\n",
            "forbidden call: os.system",
        ),
        ("def run(input_path, output_dir, params):\n    return (\n", "syntax error"),
    ],
)
def test_codeguard_rejects_dangerous_code(code: str, needle: str) -> None:
    problems = validate_skill_code(code)
    assert any(needle in p for p in problems), problems
