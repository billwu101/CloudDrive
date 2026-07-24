"""DEC-035: generated/authored skills targeting folders.

Covers the new backend surface: item_types authority + error messages,
folder-subtree collection, subtree materialization into the sandbox input,
the ingest caps, and that the sandbox accepts a directory ``input_path``.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from pathlib import Path
from typing import IO, Any, cast
from uuid import UUID, uuid4

import pytest

from app.assistant.repository import AbstractAssistantSkillRepository
from app.assistant.skills.authoring import (
    AssistantSkillService,
    _skill_item_types,
    _wrong_type_message,
)
from app.assistant.skills.sandbox import SkillSandbox
from app.core.exceptions import AppError
from app.drive.repository import (
    AbstractDriveItemRepository,
    AbstractUserItemPreferenceRepository,
)
from app.drive.schemas import DriveItemSortField, ItemType
from app.drive.service import DriveService
from app.models.assistant_skill import AssistantSkill
from app.models.drive_item import DriveItem
from app.models.user_item_preference import UserItemPreference
from app.schemas.common import SortOrder
from app.storage.base import StoredObject
from app.upload.service import UploadService


def _mk(
    *,
    owner_id: UUID,
    item_type: ItemType,
    name: str,
    parent_id: UUID | None = None,
    storage_key: str | None = None,
    size_bytes: int = 0,
) -> DriveItem:
    now = datetime.now(UTC)
    return DriveItem(
        id=uuid4(),
        owner_id=owner_id,
        parent_id=parent_id,
        item_type=item_type,
        name=name,
        mime_type=None,
        extension=None,
        size_bytes=size_bytes,
        storage_key=storage_key,
        checksum_sha256=None,
        is_starred=False,
        is_deleted=False,
        deleted_at=None,
        created_by=owner_id,
        updated_by=None,
        created_at=now,
        updated_at=now,
    )


class TreeDriveItemRepo(AbstractDriveItemRepository):
    """Minimal repo backed by a flat list, resolving children by parent_id."""

    def __init__(self, items: list[DriveItem]) -> None:
        self._items = {item.id: item for item in items}

    async def get_by_id(self, item_id: UUID) -> DriveItem | None:
        return self._items.get(item_id)

    async def list_children(
        self,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        sort_by: DriveItemSortField,
        order: SortOrder,
        offset: int,
        limit: int,
    ) -> tuple[list[DriveItem], int]:
        kids = [
            it
            for it in self._items.values()
            if it.parent_id == parent_id and it.owner_id == owner_id and not it.is_deleted
        ]
        kids.sort(key=lambda it: it.name)
        return kids[offset : offset + limit], len(kids)

    async def create(
        self,
        *,
        owner_id: UUID,
        parent_id: UUID | None,
        item_type: str,
        name: str,
        created_by: UUID,
    ) -> DriveItem:  # pragma: no cover
        raise NotImplementedError

    async def update_name(self, item_id: UUID, name: str, updated_by: UUID) -> DriveItem:
        raise NotImplementedError  # pragma: no cover

    async def update_parent(
        self, item_id: UUID, parent_id: UUID | None, updated_by: UUID
    ) -> DriveItem:
        raise NotImplementedError  # pragma: no cover

    async def name_exists_in_parent(
        self,
        name: str,
        parent_id: UUID | None,
        owner_id: UUID,
        *,
        exclude_id: UUID | None = None,
    ) -> bool:
        return False  # pragma: no cover


class _PrefRepo(AbstractUserItemPreferenceRepository):
    async def get_preference(self, user_id: UUID, item_id: UUID) -> UserItemPreference | None:
        return None  # pragma: no cover

    async def upsert_preference(
        self, user_id: UUID, item_id: UUID, *, is_starred: bool
    ) -> UserItemPreference:
        raise NotImplementedError  # pragma: no cover

    async def get_starred_ids(self, user_id: UUID, item_ids: list[UUID]) -> set[UUID]:
        return set()  # pragma: no cover


class FakeStorage:
    """In-memory StorageProvider: only open_read is exercised here."""

    def __init__(self, blobs: dict[str, bytes]) -> None:
        self._blobs = blobs

    async def save(self, key: str, data: IO[bytes], *, size: int | None = None) -> None:
        self._blobs[key] = data.read()

    async def open_read(self, key: str) -> AsyncGenerator[bytes, None]:
        yield self._blobs[key]

    async def delete(self, key: str) -> None:  # pragma: no cover
        self._blobs.pop(key, None)

    async def exists(self, key: str) -> bool:  # pragma: no cover
        return key in self._blobs

    async def get_size(self, key: str) -> int:  # pragma: no cover
        return len(self._blobs[key])

    async def list_objects(self) -> list[StoredObject]:  # pragma: no cover
        return []


def _service(
    *,
    items: list[DriveItem],
    blobs: dict[str, bytes] | None = None,
    skills: list[AssistantSkill] | None = None,
) -> AssistantSkillService:
    drive = DriveService(item_repo=TreeDriveItemRepo(items), pref_repo=_PrefRepo())
    return AssistantSkillService(
        repo=_SkillRepo(skills or []),
        drive_service=drive,
        sandbox=SkillSandbox(timeout_sec=30),
        uploads=cast(UploadService, object()),
        storage=cast("object", FakeStorage(blobs or {})),  # type: ignore[arg-type]
    )


class _SkillRepo(AbstractAssistantSkillRepository):
    def __init__(self, skills: list[AssistantSkill]) -> None:
        self._skills = {s.id: s for s in skills}

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = self._skills.get(skill_id)
        return skill if skill and skill.user_id == user_id else None

    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None:
        return None  # pragma: no cover

    async def list_by_status(
        self, *, user_id: UUID, status: str | None = None
    ) -> list[AssistantSkill]:
        return []  # pragma: no cover

    async def create_or_replace_pending(
        self, *, user_id: UUID, name: str, description: str, manifest: dict[str, Any], code: str
    ) -> AssistantSkill:
        raise NotImplementedError  # pragma: no cover

    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        raise NotImplementedError  # pragma: no cover

    async def update(
        self,
        *,
        user_id: UUID,
        skill_id: UUID,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill | None:
        raise NotImplementedError  # pragma: no cover

    async def set_chat_enabled(
        self, *, user_id: UUID, skill_id: UUID, enabled: bool
    ) -> AssistantSkill | None:
        raise NotImplementedError  # pragma: no cover

    async def delete(self, *, user_id: UUID, skill_id: UUID) -> bool:
        return False  # pragma: no cover


def _skill(owner_id: UUID, *, name: str, item_types: list[str], code: str = "") -> AssistantSkill:
    now = datetime.now(UTC)
    return AssistantSkill(
        id=uuid4(),
        user_id=owner_id,
        name=name,
        description="d",
        manifest={
            "name": name,
            "description": "d",
            "version": "1.0.0",
            "ui": {"context_menu": [{"label": name, "handler": name, "item_types": item_types}]},
        },
        code=code,
        status="installed",
        chat_enabled=False,
        created_at=now,
        updated_at=now,
    )


# ── pure helpers ────────────────────────────────────────────────────────────


def test_skill_item_types_reads_declared_types() -> None:
    owner = uuid4()
    assert _skill_item_types(_skill(owner, name="a", item_types=["FILE"])) == {"FILE"}
    assert _skill_item_types(_skill(owner, name="a", item_types=["FOLDER"])) == {"FOLDER"}
    assert _skill_item_types(_skill(owner, name="a", item_types=["FILE", "FOLDER"])) == {
        "FILE",
        "FOLDER",
    }


def test_skill_item_types_defaults_to_file_when_absent() -> None:
    owner = uuid4()
    skill = _skill(owner, name="a", item_types=[])
    skill.manifest = {"name": "a", "ui": {"context_menu": []}}
    assert _skill_item_types(skill) == {"FILE"}


def test_wrong_type_message() -> None:
    assert _wrong_type_message({"FILE"}) == "This skill runs on a file"
    assert _wrong_type_message({"FOLDER"}) == "This skill runs on a folder"
    assert _wrong_type_message({"FILE", "FOLDER"}) == "This skill runs on a file or a folder"


# ── folder subtree collection ───────────────────────────────────────────────


async def test_collect_folder_files_walks_nested_subtree() -> None:
    owner = uuid4()
    root = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="root")
    sub = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="sub", parent_id=root.id)
    f1 = _mk(
        owner_id=owner, item_type=ItemType.FILE, name="a.txt", parent_id=root.id, storage_key="k1"
    )
    f2 = _mk(
        owner_id=owner, item_type=ItemType.FILE, name="b.txt", parent_id=sub.id, storage_key="k2"
    )
    no_key = _mk(owner_id=owner, item_type=ItemType.FILE, name="c.txt", parent_id=root.id)
    drive = DriveService(
        item_repo=TreeDriveItemRepo([root, sub, f1, f2, no_key]), pref_repo=_PrefRepo()
    )

    files = await drive.collect_folder_files(owner, root.id)
    rels = {rel for rel, _ in files}

    assert rels == {"a.txt", "sub/b.txt"}  # folder + storage_key-less file excluded


# ── materialization + caps ──────────────────────────────────────────────────


async def test_materialize_input_folder_mirrors_subtree(tmp_path: Path) -> None:
    owner = uuid4()
    root = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="pics")
    sub = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="inner", parent_id=root.id)
    f1 = _mk(
        owner_id=owner,
        item_type=ItemType.FILE,
        name="x.txt",
        parent_id=root.id,
        storage_key="k1",
        size_bytes=3,
    )
    f2 = _mk(
        owner_id=owner,
        item_type=ItemType.FILE,
        name="y.txt",
        parent_id=sub.id,
        storage_key="k2",
        size_bytes=3,
    )
    svc = _service(items=[root, sub, f1, f2], blobs={"k1": b"xxx", "k2": b"yyy"})

    input_path = await svc._materialize_input(owner, root, tmp_path)

    assert input_path.is_dir()
    assert (input_path / "x.txt").read_bytes() == b"xxx"
    assert (input_path / "inner" / "y.txt").read_bytes() == b"yyy"


async def test_materialize_input_folder_rejects_too_many_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = uuid4()
    root = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="big")
    kids = [
        _mk(
            owner_id=owner,
            item_type=ItemType.FILE,
            name=f"f{i}.txt",
            parent_id=root.id,
            storage_key=f"k{i}",
            size_bytes=1,
        )
        for i in range(3)
    ]
    from app.core import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "assistant_folder_max_files", 2, raising=True)
    svc = _service(items=[root, *kids], blobs={f"k{i}": b"z" for i in range(3)})

    with pytest.raises(AppError, match="too many files"):
        await svc._materialize_input(owner, root, tmp_path)


async def test_materialize_input_folder_rejects_too_large(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = uuid4()
    root = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="big")
    f = _mk(
        owner_id=owner,
        item_type=ItemType.FILE,
        name="huge.bin",
        parent_id=root.id,
        storage_key="k",
        size_bytes=10_000,
    )
    from app.core import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "assistant_folder_max_bytes", 100, raising=True)
    svc = _service(items=[root, f], blobs={"k": b"z"})

    with pytest.raises(AppError, match="too large"):
        await svc._materialize_input(owner, root, tmp_path)


async def test_materialize_input_empty_folder_raises(tmp_path: Path) -> None:
    owner = uuid4()
    root = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="empty")
    svc = _service(items=[root])

    with pytest.raises(AppError, match="no files"):
        await svc._materialize_input(owner, root, tmp_path)


# ── item_types authority via execute_skill ──────────────────────────────────


async def test_execute_file_only_skill_on_folder_rejected() -> None:
    owner = uuid4()
    folder = _mk(owner_id=owner, item_type=ItemType.FOLDER, name="f")
    skill = _skill(owner, name="file_skill", item_types=["FILE"])
    svc = _service(items=[folder], skills=[skill])

    with pytest.raises(AppError, match="This skill runs on a file"):
        await svc.execute_skill(user_id=owner, skill_id=skill.id, item_id=folder.id)


async def test_execute_folder_only_skill_on_file_rejected() -> None:
    owner = uuid4()
    file_item = _mk(owner_id=owner, item_type=ItemType.FILE, name="a.txt", storage_key="k")
    skill = _skill(owner, name="folder_skill", item_types=["FOLDER"])
    svc = _service(items=[file_item], skills=[skill], blobs={"k": b"x"})

    with pytest.raises(AppError, match="This skill runs on a folder"):
        await svc.execute_skill(user_id=owner, skill_id=skill.id, item_id=file_item.id)


# ── sandbox accepts a directory input_path ──────────────────────────────────


async def test_sandbox_runs_on_directory_input(tmp_path: Path) -> None:
    src = tmp_path / "folder"
    (src / "sub").mkdir(parents=True)
    (src / "a.txt").write_text("1")
    (src / "sub" / "b.txt").write_text("2")
    code = (
        "import os\n"
        "def run(input_path, output_dir, params):\n"
        "    names = []\n"
        "    for root, dirs, files in os.walk(input_path):\n"
        "        names.extend(files)\n"
        "    out = os.path.join(output_dir, 'listing.txt')\n"
        "    with open(out, 'w') as fh:\n"
        "        fh.write('\\n'.join(sorted(names)))\n"
        "    return {'count': len(names), 'item_type': params.get('item_type')}\n"
    )
    sandbox = SkillSandbox(timeout_sec=30)
    try:
        result = sandbox.run(code=code, input_path=src, params={"item_type": "FOLDER"})
    finally:
        sandbox.cleanup()

    assert result.ok
    assert result.output == {"count": 2, "item_type": "FOLDER"}
