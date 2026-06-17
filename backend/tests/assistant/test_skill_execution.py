from __future__ import annotations

import io
import sys
import zipfile
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.assistant.skills.authoring import AssistantSkillService
from app.assistant.skills.sandbox import SkillSandbox
from app.core.exceptions import AppError
from app.drive.schemas import ItemType
from app.models.assistant_skill import AssistantSkill

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="sandbox relies on POSIX process groups"
)

# A realistic generated skill: extract a zip archive into output_dir.
_ZIP_SKILL_CODE = (
    "import zipfile\n"
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    names = []\n"
    "    with zipfile.ZipFile(input_path) as z:\n"
    "        z.extractall(output_dir)\n"
    "        names = z.namelist()\n"
    "    return {'extracted': names}\n"
)


def _zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("readme.txt", "hello")
        z.writestr("docs/guide.md", "# guide")
    return buf.getvalue()


def _installed_zip_skill(user_id: UUID) -> AssistantSkill:
    now = datetime.now(UTC)
    return AssistantSkill(
        id=uuid4(),
        user_id=user_id,
        name="decompress_zip",
        description="Extract a zip archive.",
        manifest={"name": "decompress_zip", "description": "x", "version": "1.0.0", "ui": {}},
        code=_ZIP_SKILL_CODE,
        status="installed",
        created_at=now,
        updated_at=now,
    )


class _Repo:
    def __init__(self, skill: AssistantSkill) -> None:
        self._skill = skill

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        return self._skill if skill_id == self._skill.id else None


class _Drive:
    def __init__(self, source: SimpleNamespace) -> None:
        self._source = source
        self.created: list[tuple[UUID | None, str]] = []

    async def get_raw_item(self, *, user_id: UUID, item_id: UUID) -> SimpleNamespace:
        return self._source

    async def create_folder(self, user_id: UUID, parent_id: UUID | None, name: str) -> Any:
        self.created.append((parent_id, name))
        return SimpleNamespace(id=uuid4(), name=name)


class _Storage:
    def __init__(self, data: bytes) -> None:
        self._data = data

    async def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        yield self._data


class _Uploads:
    def __init__(self) -> None:
        self.uploaded: list[tuple[UUID | None, str, int]] = []

    async def upload_simple(
        self,
        user_id: UUID,
        parent_id: UUID | None,
        filename: str,
        stream: AsyncGenerator[bytes, None],
        size_bytes: int,
        mime_type: str | None = None,
    ) -> Any:
        total = 0
        async for chunk in stream:
            total += len(chunk)
        assert total == size_bytes
        self.uploaded.append((parent_id, filename, size_bytes))
        return SimpleNamespace(name=filename)


def _service(skill: AssistantSkill, drive: _Drive, uploads: _Uploads, storage: _Storage) -> Any:
    return AssistantSkillService(
        repo=skill_repo_cast(_Repo(skill)),
        drive_service=drive,  # type: ignore[arg-type]
        sandbox=SkillSandbox(timeout_sec=15),
        uploads=uploads,  # type: ignore[arg-type]
        storage=storage,  # type: ignore[arg-type]
    )


def skill_repo_cast(repo: _Repo) -> Any:
    return repo


async def test_generated_skill_extracts_and_ingests_files() -> None:
    user_id = uuid4()
    skill = _installed_zip_skill(user_id)
    source = SimpleNamespace(
        id=uuid4(),
        name="bundle.zip",
        item_type=ItemType.FILE,
        storage_key="users/x/files/y/v1",
        parent_id=None,
    )
    drive = _Drive(source)
    uploads = _Uploads()
    service = _service(skill, drive, uploads, _Storage(_zip_bytes()))

    result = await service.execute_skill(user_id=user_id, skill_id=skill.id, item_id=source.id)

    assert result.skill_name == "decompress_zip"
    # Both archive members were ingested as drive items.
    ingested = {name for _, name, _ in uploads.uploaded}
    assert ingested == {"readme.txt", "guide.md"}
    # A destination folder named after the archive stem was created,
    # plus a nested "docs" folder for the nested member.
    folder_names = {name for _, name in drive.created}
    assert "bundle (extracted)" in folder_names
    assert "docs" in folder_names
    assert result.output["summary"]["extracted"]


async def test_generated_skill_surfaces_sandbox_failure() -> None:
    user_id = uuid4()
    bad = _installed_zip_skill(user_id)
    bad.code = "def run(input_path, output_dir, params):\n    raise ValueError('boom')\n"
    source = SimpleNamespace(
        id=uuid4(),
        name="bundle.zip",
        item_type=ItemType.FILE,
        storage_key="k",
        parent_id=None,
    )
    drive = _Drive(source)
    uploads = _Uploads()
    service = _service(bad, drive, uploads, _Storage(_zip_bytes()))

    with pytest.raises(AppError, match="Skill execution failed"):
        await service.execute_skill(user_id=user_id, skill_id=bad.id, item_id=source.id)
    assert uploads.uploaded == []  # nothing ingested on failure
