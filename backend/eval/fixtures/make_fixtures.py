"""Generate deterministic input fixtures for execution-mode eval cases.

Run once and commit the outputs:  python -m eval.fixtures.make_fixtures
"""

from __future__ import annotations

import io
import tarfile
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
    print("fixtures:", sorted(p.name for p in FIXTURES.glob("sample.*")))


if __name__ == "__main__":
    main()
