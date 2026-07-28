"""Generate deterministic input fixtures for execution-mode eval cases.

Run once and commit the outputs:  python -m eval.fixtures.make_fixtures
"""

from __future__ import annotations

import base64
import bz2
import csv
import gzip
import io
import json
import lzma
import tarfile
import zipfile
import zlib
from pathlib import Path

from PIL import Image

FIXTURES = Path(__file__).resolve().parent

# Known text content — its hashes/line counts are asserted by the eval cases.
SAMPLE_TXT = b"hello world\nsecond line\nthird line\n"


def _make_txt() -> None:
    (FIXTURES / "sample.txt").write_bytes(SAMPLE_TXT)


def _make_tar() -> None:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for name, body in [("alpha.txt", b"AAA\n"), ("docs/beta.txt", b"BBB\n")]:
            info = tarfile.TarInfo(name=name)
            info.size = len(body)
            tar.addfile(info, io.BytesIO(body))
    (FIXTURES / "sample.tar").write_bytes(buf.getvalue())


# --- M4 codegen smoke fixtures (2026-07-28) --------------------------------
#
# The smoke test used to feed sample.txt to every generated skill. Format-specific
# skills (decode / extract / image / pdf / json / csv) then produced nothing and
# were scored as failures — 48 of 99 M4 cases, purely an artefact of the input.
# Proven by A/B on one real generated skill (invert_image_colors): sample.txt →
# no output, sample.png → correct output. Each skill family now gets an input it
# can actually work on, so the check measures the model rather than the fixture.


def _make_archives() -> None:
    """One archive per format an extract_* skill may be generated for."""

    members = [("alpha.txt", b"AAA\n"), ("docs/beta.txt", b"BBB\n")]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, body in members:
            zf.writestr(name, body)
    (FIXTURES / "sample.zip").write_bytes(buf.getvalue())

    tar_bytes = (FIXTURES / "sample.tar").read_bytes()
    (FIXTURES / "sample.tar.gz").write_bytes(gzip.compress(tar_bytes, mtime=0))
    (FIXTURES / "sample.txt.gz").write_bytes(gzip.compress(SAMPLE_TXT, mtime=0))
    (FIXTURES / "sample.txt.bz2").write_bytes(bz2.compress(SAMPLE_TXT))
    (FIXTURES / "sample.txt.xz").write_bytes(lzma.compress(SAMPLE_TXT))
    # 7z needs py7zr (already a backend dependency for the built-in skill).
    import py7zr

    path = FIXTURES / "sample.7z"
    with py7zr.SevenZipFile(path, "w") as archive:
        archive.writestr(SAMPLE_TXT.decode(), "alpha.txt")


def _make_encoded() -> None:
    """Inputs a decoder can actually decode (of the *same* SAMPLE_TXT)."""

    (FIXTURES / "sample.base64.txt").write_bytes(base64.b64encode(SAMPLE_TXT))
    (FIXTURES / "sample.base32.txt").write_bytes(base64.b32encode(SAMPLE_TXT))
    (FIXTURES / "sample.hex.txt").write_bytes(SAMPLE_TXT.hex().encode())
    (FIXTURES / "sample.ascii85.txt").write_bytes(base64.a85encode(SAMPLE_TXT))


def _make_data() -> None:
    rows = [
        {"name": "alpha", "size": "10", "kind": "doc"},
        {"name": "beta", "size": "20", "kind": "image"},
        {"name": "gamma", "size": "30", "kind": "doc"},
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["name", "size", "kind"], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    (FIXTURES / "sample.csv").write_text(buf.getvalue(), encoding="utf-8")
    (FIXTURES / "sample.json").write_text(
        json.dumps({"items": rows, "total": len(rows)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _make_png() -> None:
    # 64x64 solid image; a thumbnailer must shrink it to <= 32px.
    Image.new("RGB", (64, 64), (10, 120, 200)).save(FIXTURES / "sample.png", "PNG")


def _make_pdf() -> None:
    # Minimal one-page PDF with a FlateDecode-compressed text stream. pypdf reads
    # it, and so do generated skills that decompress FlateDecode content.
    text = b"BT /F1 24 Tf 50 100 Td (Hello PDF Eval) Tj ET"
    stream = zlib.compress(text)
    objs = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]"
        b"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
        b"<</Length %d/Filter/FlateDecode>>stream\n%s\nendstream" % (len(stream), stream),
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj" % i + body + b"endobj\n"
    xref_pos = len(out)
    out += b"xref\n0 %d\n" % (len(objs) + 1)
    out += b"0000000000 65535 f \n"
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF" % (
        len(objs) + 1,
        xref_pos,
    )
    (FIXTURES / "sample.pdf").write_bytes(bytes(out))


def main() -> None:
    _make_txt()
    _make_tar()
    _make_png()
    _make_pdf()
    _make_archives()
    _make_encoded()
    _make_data()
    print("fixtures:", sorted(p.name for p in FIXTURES.glob("sample.*")))


if __name__ == "__main__":
    main()
