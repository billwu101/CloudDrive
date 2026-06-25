"""Static validation of generated skill code (defense-in-depth before sandbox).

This is the "靜態驗證" step of the generation subflow: a cheap AST scan that
rejects obviously-dangerous generated code *before* it is shown to the user for
approval, and well before it ever reaches the sandbox. It is not a security
boundary on its own — the :class:`~app.assistant.skills.sandbox.SkillSandbox`
runtime audit guard is — but it catches the easy cases and gives the human
reviewer a clean artifact.

Contract enforced: a module-level ``def run(input_path, output_dir, params)``.
"""

from __future__ import annotations

import ast

# Modules a generated skill must never import. File/archive work only needs the
# stdlib (zipfile/tarfile/pathlib/json/...) plus the archive libs we vendor.
_FORBIDDEN_IMPORTS = frozenset(
    {
        "subprocess",
        "socket",
        "ssl",
        "ctypes",
        "cffi",
        "multiprocessing",
        "threading",
        "asyncio",
        "requests",
        "httpx",
        "urllib",
        "http",
        "ftplib",
        "smtplib",
        "telnetlib",
        "paramiko",
        "pty",
        "signal",
        "importlib",
        "pickle",
        "marshal",
        "code",
        "codeop",
        "winreg",
        "fcntl",
        "mmap",
    }
)

# Bare names whose use is disallowed (dynamic code execution / introspection).
_FORBIDDEN_NAMES = frozenset(
    {"eval", "exec", "compile", "__import__", "globals", "vars", "breakpoint", "input"}
)

# os.<attr> calls that shell out or spawn — blocked even though `os` is allowed
# for path operations.
_FORBIDDEN_OS_ATTRS = frozenset(
    {
        "system",
        "popen",
        "execv",
        "execve",
        "execvp",
        "execl",
        "execlp",
        "spawnv",
        "spawnl",
        "posix_spawn",
        "startfile",
        "fork",
        "forkpty",
        "kill",
        "killpg",
        "setuid",
        "setgid",
    }
)

_REQUIRED_PARAMS = ("input_path", "output_dir", "params")


def validate_skill_code(code: str) -> list[str]:
    """Return a list of human-readable problems; empty means the code is clean."""

    problems: list[str] = []
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return [f"syntax error: {exc.msg} (line {exc.lineno})"]

    _check_run_contract(tree, problems)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in _FORBIDDEN_IMPORTS:
                    problems.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                problems.append(f"forbidden import: from {node.module}")
        elif isinstance(node, ast.Name) and node.id in _FORBIDDEN_NAMES:
            problems.append(f"forbidden use of '{node.id}'")
        elif isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in _FORBIDDEN_OS_ATTRS
            ):
                problems.append(f"forbidden call: os.{node.attr}")
            if (
                node.attr.startswith("__")
                and node.attr.endswith("__")
                and node.attr
                not in (
                    "__name__",
                    "__doc__",
                )
            ):
                problems.append(f"forbidden dunder access: {node.attr}")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for problem in problems:
        if problem not in seen:
            seen.add(problem)
            unique.append(problem)
    return unique


def _check_run_contract(tree: ast.Module, problems: list[str]) -> None:
    run_fn = next(
        (node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "run"),
        None,
    )
    if run_fn is None:
        problems.append("missing required entrypoint: def run(input_path, output_dir, params)")
        return
    arg_names = [arg.arg for arg in run_fn.args.args]
    if arg_names[:3] != list(_REQUIRED_PARAMS):
        problems.append(
            "run() must take exactly (input_path, output_dir, params); got "
            f"({', '.join(arg_names) or 'no args'})"
        )
