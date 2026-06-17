"""Single-layer codegen sub-agent (HARNESS 04).

When the planner finds a capability that is neither built-in nor installed, the
generation subflow spins up this sub-agent in its own short context to author
the missing skill: it asks the model for a ``{manifest, code}`` pair, then
statically validates both (manifest schema + :mod:`codeguard` AST scan). On
problems it feeds them back and re-asks, up to a small bound. It never executes
anything — the result is a *proposal* that still requires user approval and a
sandbox run before install.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage
from app.assistant.llm.router import ModelRouter
from app.assistant.skills.codeguard import validate_skill_code
from app.assistant.skills.manifest import validate_manifest
from app.core.exceptions import AppError

_CODEGEN_SYSTEM = (
    "You are CloudDrive's skill author. Generate a NEW skill that performs a single "
    "file operation the user asked for but which is not built in.\n"
    "Respond with ONE JSON object only (no prose, no code fences):\n"
    '{"name": str, "description": str, "version": "1.0.0", '
    '"code": str, "ui": {"context_menu": [{"label": str, "handler": str, '
    '"item_types": ["FILE"|"FOLDER"]}]}}.\n'
    "Rules for `code` (a Python source string):\n"
    "- Define exactly: def run(input_path, output_dir, params): ...\n"
    "- input_path is a read-only source file. Write outputs ONLY under output_dir.\n"
    "- Return a small JSON-serializable dict summarizing what happened.\n"
    "- Allowed libraries (use the RIGHT one for the format):\n"
    "    standard library — zipfile, tarfile, gzip, bz2, lzma, pathlib, os.path, json, csv, "
    "io, shutil, hashlib (md5/sha1/sha256/...), base64, zlib, re, struct;\n"
    "    py7zr — for .7z archives;\n"
    "    PIL (Pillow) — for images (thumbnail/resize/convert/grayscale), `from PIL import Image`;\n"
    "    pypdf — for PDFs (text extraction/pages/metadata): `from pypdf import PdfReader`.\n"
    "  Prefer these real libraries over hand-rolled parsers (e.g. use pypdf for PDF text, "
    "not a custom stream parser).\n"
    "- FORBIDDEN: network (socket/urllib/requests), subprocess/os.system, eval/exec, "
    "ctypes, threads. No writing outside output_dir.\n"
    "Rules for `name`: lowercase identifier ([a-z][a-z0-9_]+). Every context_menu "
    "handler MUST equal `name`.\n"
)


@dataclass
class CodegenResult:
    ok: bool
    name: str = ""
    description: str = ""
    manifest: dict[str, Any] | None = None
    code: str = ""
    problems: list[str] = field(default_factory=list)
    reply: str = ""


def build_codegen_prompt(request: str) -> str:
    return f"{_CODEGEN_SYSTEM}\nUser request: {request}"


def _extract_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text[:4].lower() == "json":
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def _split_manifest_and_code(content: str) -> tuple[dict[str, Any], str] | None:
    try:
        data = json.loads(_extract_json(content))
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict) or "code" not in data:
        return None
    code = data.get("code")
    if not isinstance(code, str):
        return None
    manifest = {
        "name": data.get("name", ""),
        "description": data.get("description", ""),
        "version": data.get("version", "1.0.0"),
        "ui": data.get("ui", {"context_menu": []}),
    }
    return manifest, code


def _validate(manifest_raw: dict[str, Any], code: str) -> tuple[dict[str, Any] | None, list[str]]:
    problems: list[str] = []
    validated: dict[str, Any] | None = None
    try:
        validated = validate_manifest(manifest_raw).model_dump(mode="json")
    except AppError as exc:
        problems.append(f"manifest: {exc.message}")
    problems.extend(validate_skill_code(code))
    return validated, problems


class CodegenSubAgent:
    def __init__(
        self,
        *,
        llm: ModelRouter,
        context: ContextManager,
        num_ctx: int,
        max_repair: int = 3,
    ) -> None:
        self._llm = llm
        self._context = context
        self._num_ctx = num_ctx
        self._max_repair = max(0, max_repair)

    async def author(self, *, request: str) -> CodegenResult:
        messages = [
            LLMMessage(role="system", content=build_codegen_prompt(request)),
            LLMMessage(role="user", content=request),
        ]

        for attempt in range(self._max_repair + 1):
            # No router-level validator: author()'s own loop is the retry
            # mechanism, and a malformed reply should degrade to a clean
            # ok=False rather than exhaust the router and raise.
            response = await self._llm.chat(
                self._context.trim(messages),
                [],
                num_ctx=self._num_ctx,
            )
            parsed = _split_manifest_and_code(response.content)
            if parsed is None:
                # Invalid JSON is also retryable — earlier this returned
                # immediately, which is why complex prompts occasionally failed
                # outright. Repair it like a validation problem.
                problems = ["respond with ONE valid JSON object only (no prose, no code fences)"]
            else:
                manifest_raw, code = parsed
                validated, problems = _validate(manifest_raw, code)
                if not problems and validated is not None:
                    return CodegenResult(
                        ok=True,
                        name=validated["name"],
                        description=validated["description"],
                        manifest=validated,
                        code=code,
                        reply=f"I drafted a skill named {validated['name']}.",
                    )
            if attempt < self._max_repair:
                messages.append(LLMMessage(role="assistant", content=response.content))
                messages.append(
                    LLMMessage(
                        role="user",
                        content=(
                            "Your generated skill was rejected: "
                            + "; ".join(problems)
                            + ". Fix these and resend the single JSON object."
                        ),
                    )
                )

        # Repairs exhausted — return the last set of problems, never code we
        # could not validate.
        return CodegenResult(
            ok=False,
            problems=problems,
            reply="I couldn't generate a safe, valid skill for that request.",
        )
