"""Is what a generated skill wrote actually usable? (2026-07-29, alfred)

``codegen_smoke`` established that the generated code *runs* and writes at
least one file. That leaves the question alfred asked next — 功能不對、程式碼的結果不對、
做錯了根本就沒有意義 — unanswered: a skill that writes a 0-byte
"archive", a truncated PNG, or a wrong checksum passes a file-exists check
while being useless.

Full per-skill correctness needs a reference implementation for each of the
100 generated skills, which is out of scope (and was explicitly deferred). What
IS general — and is what this module does — falls into three tiers:

1. **Non-empty.** A zero-byte output is never a result.
2. **Parseable as what its extension claims.** A ``.zip`` that ``zipfile``
   cannot open, a ``.png`` Pillow cannot decode, a ``.pdf`` with no pages, a
   ``.json`` that does not parse. No expected value needed — the format itself
   is the oracle.
3. **Checksums, which are verifiable without a reference.** Hash skills are the
   single most common thing the model generates. A hex token in the output must
   be the input's digest under *some* stdlib algorithm of that length — the
   length alone does not name the algorithm (sha256, sha3_256 and blake2s all
   produce 64 hex chars), so assuming one turns a correct skill into a
   failure.

Every check degrades to "unchecked" rather than "failed" when it cannot be
performed (missing optional library, unreadable bytes), so this never invents
failures it cannot substantiate.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import TypedDict


class OutputReport(TypedDict):
    """What ``check_outputs`` found. Typed so callers can read ``problems``
    without casting."""

    ok: bool
    problems: list[str]
    checked_files: int


def _fixed_length_algorithms() -> dict[int, tuple[str, ...]]:
    """Hex-digest length → every stdlib algorithm that produces that length.

    Keyed on length rather than name because that is all a bare hex token in an
    output file tells us. Several algorithms share a length (sha256, sha3_256
    and blake2s are all 64 hex chars), so a token is only wrong if it matches
    NONE of them — assuming sha256 because the length fits cost a real EC3 case
    a false failure: the skill had computed a correct blake2s.
    """

    by_length: dict[int, list[str]] = {}
    for name in sorted(hashlib.algorithms_guaranteed):
        if name.startswith("shake"):
            continue  # variable-length output; a bare token proves nothing
        try:
            length = len(hashlib.new(name).hexdigest())
        except (ValueError, TypeError):
            continue
        by_length.setdefault(length, []).append(name)
    return {length: tuple(names) for length, names in by_length.items()}


_ALGORITHMS_BY_LENGTH = _fixed_length_algorithms()
_HEX_TOKEN = re.compile(r"\b[0-9a-fA-F]{32,128}\b")
# Outputs larger than this are not scanned for digest claims (a hash report is
# tiny; decoding a big binary as text just to search it is wasted work).
_MAX_TEXT_SCAN_BYTES = 1_000_000


def _digests(path: Path) -> dict[int, set[str]]:
    """Every digest of ``path`` a generated skill might plausibly report,
    grouped by hex length (see ``_fixed_length_algorithms``).

    Both the raw bytes and the text with trailing whitespace stripped: a skill
    that reads the file as text and hashes ``content.strip()`` is doing
    something defensible, and flagging it would be a false alarm. A FOLDER
    fixture is a directory of files; any member's digest is fair game.
    """

    sources = sorted(p for p in path.rglob("*") if p.is_file()) if path.is_dir() else [path]
    variants: list[bytes] = []
    for source in sources:
        data = source.read_bytes()
        variants.append(data)
        if data.strip() != data:
            variants.append(data.strip())
    out: dict[int, set[str]] = {length: set() for length in _ALGORITHMS_BY_LENGTH}
    for variant in variants:
        for length, names in _ALGORITHMS_BY_LENGTH.items():
            for name in names:
                out[length].add(hashlib.new(name, variant).hexdigest())
    return out


def _check_format(path: Path) -> str | None:
    """Problem string if the file cannot be parsed as its extension claims."""

    suffix = path.suffix.lower()
    try:
        if suffix == ".zip":
            with zipfile.ZipFile(path) as archive:
                if archive.testzip() is not None:
                    return f"{path.name}: zip contains a corrupt member"
        elif suffix == ".7z":
            import py7zr  # optional, only needed here

            with py7zr.SevenZipFile(path) as archive:
                archive.getnames()
        elif suffix in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}:
            from PIL import Image

            with Image.open(path) as image:
                image.verify()
        elif suffix == ".pdf":
            from pypdf import PdfReader

            if len(PdfReader(str(path)).pages) == 0:
                return f"{path.name}: PDF has no pages"
        elif suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
    except ImportError:
        return None  # optional library absent — unchecked, not failed
    except Exception as exc:  # any parse failure IS the finding
        return f"{path.name}: not a valid {suffix.lstrip('.')} ({type(exc).__name__}: {exc})"
    return None


def _check_digests(path: Path, source: Path) -> str | None:
    """Problem string if the file reports a digest that is not the input's."""

    # Keyed on "does it decode as text", not on the extension: hash skills name
    # their output sample.txt.md5, sample.sha256, or nothing at all, and an
    # extension allow-list missed every one of those.
    if path.stat().st_size > _MAX_TEXT_SCAN_BYTES:
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="strict")
    except (UnicodeDecodeError, OSError):
        return None  # binary output — no digest claim to read
    tokens = {token.lower() for token in _HEX_TOKEN.findall(text)}
    if not tokens:
        return None
    expected = _digests(source)
    for token in sorted(tokens):
        candidates = expected.get(len(token))
        if not candidates:
            continue  # a hex blob of some other length is not a digest claim
        if token not in candidates:
            algorithms = "/".join(_ALGORITHMS_BY_LENGTH[len(token)])
            return (
                f"{path.name}: reports {token}, which is not the input's digest "
                f"under any {len(token)}-hex algorithm ({algorithms})"
            )
    return None


def check_outputs(output_dir: Path, source: Path) -> OutputReport:
    """Inspect everything a skill wrote. ``source`` is the fixture it was given.

    Returns ``{"ok": bool, "problems": [str], "checked_files": int}``. An empty
    ``output_dir`` is the caller's concern (``codegen_smoke`` already treats
    "no files" as a failure), so it is reported as ok here with zero files
    checked.
    """

    files = [p for p in sorted(output_dir.rglob("*")) if p.is_file()]
    problems: list[str] = []
    for path in files:
        if path.stat().st_size == 0:
            problems.append(f"{path.name}: empty file (0 bytes)")
            continue
        for problem in (_check_format(path), _check_digests(path, source)):
            if problem:
                problems.append(problem)
    return {"ok": not problems, "problems": problems, "checked_files": len(files)}
