"""What a generated skill wrote must be usable, not merely present.

Each test here is a shape the previous file-exists-only check waved through.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path

from eval.output_checks import check_outputs


def _fixture(tmp_path: Path, data: bytes = b"hello smoke test\n") -> Path:
    source = tmp_path / "sample.txt"
    source.write_bytes(data)
    return source


def _outputs(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    return out


def test_an_empty_output_file_is_not_a_result(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    (out / "result.zip").write_bytes(b"")

    report = check_outputs(out, source)

    assert report["ok"] is False
    assert "empty file (0 bytes)" in report["problems"][0]


def test_a_zip_that_cannot_be_opened_is_reported(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    (out / "archive.zip").write_bytes(b"PK\x03\x04 definitely not a zip")

    report = check_outputs(out, source)

    assert report["ok"] is False
    assert "not a valid zip" in report["problems"][0]


def test_a_real_zip_passes(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr("sample.txt", "hello smoke test\n")
    (out / "archive.zip").write_bytes(buf.getvalue())

    assert check_outputs(out, source) == {"ok": True, "problems": [], "checked_files": 1}


def test_a_wrong_checksum_is_caught_without_any_reference_implementation(
    tmp_path: Path,
) -> None:
    """The most common generated skill is a hash. Its answer is verifiable from
    the input alone — no expected value has to be written by hand."""

    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    (out / "sample.txt.md5").write_text("d41d8cd98f00b204e9800998ecf8427e  sample.txt\n")

    report = check_outputs(out, source)

    assert report["ok"] is False
    assert "is not the input's digest" in report["problems"][0]
    assert "32-hex" in report["problems"][0]


def test_a_digest_from_another_algorithm_of_the_same_length_is_not_a_failure(
    tmp_path: Path,
) -> None:
    """sha256, sha3_256 and blake2s all produce 64 hex chars. Assuming sha256
    because the length fits failed a real M4 case whose skill had correctly
    computed a blake2s digest (gen-m4-008, 2026-07-29)."""

    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    digest = hashlib.blake2s(source.read_bytes()).hexdigest()
    (out / "sample.txt.blake2s.txt").write_text(f"{digest}  sample.txt\n")

    assert check_outputs(out, source)["ok"] is True


def test_the_correct_checksum_passes(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (out / "sample.txt.sha256").write_text(f"{digest}  sample.txt\n")

    assert check_outputs(out, source)["ok"] is True


def test_hashing_the_stripped_text_is_not_flagged(tmp_path: Path) -> None:
    """A skill that reads the file as text and hashes content.strip() is doing
    something defensible — calling that wrong would be a false alarm."""

    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    digest = hashlib.md5(source.read_bytes().strip()).hexdigest()
    (out / "hash.txt").write_text(digest)

    assert check_outputs(out, source)["ok"] is True


def test_a_folder_fixture_accepts_the_digest_of_any_member(tmp_path: Path) -> None:
    folder = tmp_path / "input"
    (folder / "sub").mkdir(parents=True)
    (folder / "a.txt").write_bytes(b"alpha")
    (folder / "sub" / "b.txt").write_bytes(b"beta")
    out = _outputs(tmp_path)
    (out / "hashes.txt").write_text(
        f"a.txt {hashlib.md5(b'alpha').hexdigest()}\nsub/b.txt {hashlib.md5(b'beta').hexdigest()}\n"
    )

    assert check_outputs(out, folder)["ok"] is True


def test_broken_json_output_is_reported(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    (out / "meta.json").write_text("{'not': json,}")

    report = check_outputs(out, source)

    assert report["ok"] is False
    assert "not a valid json" in report["problems"][0]


def test_valid_json_output_passes(tmp_path: Path) -> None:
    source = _fixture(tmp_path)
    out = _outputs(tmp_path)
    (out / "meta.json").write_text(json.dumps({"lines": 1}))

    assert check_outputs(out, source)["ok"] is True


def test_no_output_files_is_left_to_the_caller(tmp_path: Path) -> None:
    """codegen_smoke already fails a run that produced nothing; this module must
    not double-report it as a content problem."""

    assert check_outputs(_outputs(tmp_path), _fixture(tmp_path)) == {
        "ok": True,
        "problems": [],
        "checked_files": 0,
    }
