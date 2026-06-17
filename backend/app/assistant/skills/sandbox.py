"""Subprocess sandbox for executing generated skill code (HARNESS 09).

Generated skills are *not* trusted. They run in a separate, isolated Python
process with several layers of containment:

* **Process isolation** — launched with ``python -I`` (ignore env vars and user
  site), a minimal environment, and its own process group so a runaway can be
  killed wholesale.
* **Resource limits** (POSIX) — CPU time and output file size are capped via
  ``setrlimit`` in a ``preexec_fn``; wall-clock is capped by the subprocess
  timeout (the primary guard).
* **Runtime audit guard** — a permanent ``sys.addaudithook`` inside the child
  denies network access, process spawning, and any file *write* outside the
  designated output/temp directories. The hook is installed before the
  untrusted code is imported and cannot be removed by it.

The contract for generated code: a module-level
``def run(input_path: str, output_dir: str, params: dict) -> <json>``.
``input_path`` is the (read-only) source file, ``output_dir`` is the only place
writes are allowed. The returned value must be JSON-serializable.

Network cannot be blocked with full certainty across every platform, so this is
defense-in-depth layered with the static :mod:`codeguard` check — never a sole
guarantee. Generated code only reaches here after explicit user approval.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_RESULT_MARKER = "<<<SANDBOX_RESULT>>>"

# Embedded harness: written to a temp file and run as the child's entrypoint.
# Receives one argv: the path to a JSON spec {code_path, input_path, output_dir,
# allow_write, params}. Installs the audit guard, then imports and calls run().
_HARNESS = """
import importlib.util
import json
import os
import sys
import traceback

_MARKER = "<<<SANDBOX_RESULT>>>"


def _emit(payload):
    sys.stdout.write("\\n" + _MARKER + json.dumps(payload) + "\\n")
    sys.stdout.flush()


def _install_guard(allow_write):
    real = [os.path.realpath(d) for d in allow_write if d]

    def _is_allowed(path):
        rp = os.path.realpath(path)
        return any(rp == d or rp.startswith(d + os.sep) for d in real)

    def hook(event, args):
        if event.startswith("socket.") or event.startswith("http.") or event in (
            "urllib.Request",
            "ftplib.connect",
            "smtplib.connect",
        ):
            raise PermissionError("network access is blocked in the sandbox")
        if event.startswith("subprocess.") or event in (
            "os.system",
            "os.exec",
            "os.spawn",
            "os.posix_spawn",
            "os.startfile",
            "pty.spawn",
            "winreg.OpenKey",
        ):
            raise PermissionError("process execution is blocked in the sandbox")
        if event == "open":
            data = list(args) + [None, None, None]
            path, mode, flags = data[0], data[1], data[2]
            if path is None:
                return
            writing = bool(mode and any(c in str(mode) for c in "wax+"))
            if isinstance(flags, int) and flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                writing = True
            if writing and not _is_allowed(path):
                raise PermissionError("writing outside the sandbox output is blocked")

    sys.addaudithook(hook)


def _load(code_path):
    spec = importlib.util.spec_from_file_location("generated_skill", code_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    spec = json.loads(open(sys.argv[1]).read())
    _install_guard([spec["output_dir"]] + spec.get("allow_write", []))
    try:
        module = _load(spec["code_path"])
    except Exception as exc:  # noqa: BLE001
        _emit({"ok": False, "error": "failed to load generated code: " + repr(exc)})
        return
    if not hasattr(module, "run"):
        msg = "generated code must define run(input_path, output_dir, params)"
        _emit({"ok": False, "error": msg})
        return
    try:
        output = module.run(spec["input_path"], spec["output_dir"], spec.get("params") or {})
        json.dumps(output)  # ensure serializable
        _emit({"ok": True, "output": output})
    except PermissionError as exc:
        _emit({"ok": False, "error": "sandbox policy violation: " + str(exc)})
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc(limit=4)
        _emit({"ok": False, "error": repr(exc), "traceback": tb[-1500:]})


main()
"""


@dataclass
class SandboxResult:
    ok: bool
    output: Any | None = None
    error: str | None = None
    timed_out: bool = False
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    produced_files: list[str] = field(default_factory=list)


def _posix_preexec(cpu_seconds: int, fsize_bytes: int) -> Any:
    import resource  # POSIX only; imported lazily

    def _apply() -> None:
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsize_bytes, fsize_bytes))

    return _apply


class SkillSandbox:
    """Runs a generated skill's ``run()`` in an isolated subprocess."""

    def __init__(
        self,
        *,
        timeout_sec: int = 30,
        max_output_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        self._timeout = max(1, timeout_sec)
        self._max_output = max_output_bytes
        self._last_output_dir: Path | None = None
        self._last_run_dir: Path | None = None

    def run(
        self,
        *,
        code: str,
        input_path: Path,
        params: dict[str, Any] | None = None,
    ) -> SandboxResult:
        run_dir = Path(tempfile.mkdtemp(prefix="skill_sandbox_"))
        output_dir = run_dir / "output"
        tmp_dir = run_dir / "tmp"
        output_dir.mkdir()
        tmp_dir.mkdir()
        code_path = run_dir / "generated_skill.py"
        harness_path = run_dir / "_harness.py"
        spec_path = run_dir / "_spec.json"
        code_path.write_text(code, encoding="utf-8")
        harness_path.write_text(_HARNESS, encoding="utf-8")
        spec_path.write_text(
            json.dumps(
                {
                    "code_path": str(code_path),
                    "input_path": str(input_path),
                    "output_dir": str(output_dir),
                    "allow_write": [str(tmp_dir)],
                    "params": params or {},
                }
            ),
            encoding="utf-8",
        )

        env = {
            "PATH": "/usr/bin:/bin",
            "TMPDIR": str(tmp_dir),
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        preexec = None
        if os.name == "posix":
            preexec = _posix_preexec(self._timeout, self._max_output)

        start = time.monotonic()
        try:
            proc = subprocess.run(
                [sys.executable, "-I", str(harness_path), str(spec_path)],
                cwd=str(output_dir),
                env=env,
                capture_output=True,
                text=True,
                timeout=self._timeout,
                preexec_fn=preexec,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._kill_group(exc)
            duration = int((time.monotonic() - start) * 1000)
            result = SandboxResult(
                ok=False,
                error=f"sandbox timed out after {self._timeout}s",
                timed_out=True,
                duration_ms=duration,
                stdout=_as_text(exc.stdout),
                stderr=_as_text(exc.stderr),
            )
            shutil.rmtree(run_dir, ignore_errors=True)
            return result

        duration = int((time.monotonic() - start) * 1000)
        parsed = _extract_result(proc.stdout)
        produced = (
            [str(p.relative_to(output_dir)) for p in sorted(output_dir.rglob("*")) if p.is_file()]
            if output_dir.exists()
            else []
        )
        if parsed is None:
            result = SandboxResult(
                ok=False,
                error=(
                    f"sandbox produced no result (exit {proc.returncode})"
                    + (f": {proc.stderr.strip()[-500:]}" if proc.stderr else "")
                ),
                duration_ms=duration,
                stdout=proc.stdout[-2000:],
                stderr=proc.stderr[-2000:],
                produced_files=produced,
            )
        else:
            result = SandboxResult(
                ok=bool(parsed.get("ok")),
                output=parsed.get("output"),
                error=parsed.get("error"),
                duration_ms=duration,
                stdout=proc.stdout[-2000:],
                stderr=proc.stderr[-2000:],
                produced_files=produced,
            )
        # Keep the run dir alive so the caller can ingest produced files via
        # ``last_output_dir``; the caller must call ``cleanup()`` when done.
        self._last_output_dir = output_dir
        self._last_run_dir = run_dir
        return result

    @property
    def last_output_dir(self) -> Path | None:
        return self._last_output_dir

    def cleanup(self) -> None:
        if self._last_run_dir is not None:
            shutil.rmtree(self._last_run_dir, ignore_errors=True)

    @staticmethod
    def _kill_group(exc: subprocess.TimeoutExpired) -> None:
        if os.name != "posix":
            return
        # Best-effort: the child created its own session/group via setsid.
        try:
            import signal

            pid = getattr(exc, "pid", None) or 0
            if pid:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            pass


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


def _extract_result(stdout: str) -> dict[str, Any] | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(_RESULT_MARKER):
            try:
                parsed = json.loads(line[len(_RESULT_MARKER) :])
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None
