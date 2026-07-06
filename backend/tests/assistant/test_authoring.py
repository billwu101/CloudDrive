from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMMessage, LLMResponse, LLMToolDefinition
from app.assistant.llm.router import ModelRouter
from app.assistant.repository import AbstractAssistantSkillRepository
from app.assistant.skills.authoring import AssistantSkillService
from app.assistant.subagent import CodegenSubAgent
from app.drive.service import DriveService
from app.models.assistant_skill import AssistantSkill

_GOOD_CODE = (
    "import zipfile\n"
    "import os\n"
    "def run(input_path, output_dir, params):\n"
    "    with zipfile.ZipFile(input_path) as z:\n"
    "        z.extractall(output_dir)\n"
    "    return {'files': os.listdir(output_dir)}\n"
)


def _proposal_json(name: str = "decompress_7z", code: str = _GOOD_CODE) -> str:
    return json.dumps(
        {
            "name": name,
            "description": "Extract an archive.",
            "version": "1.0.0",
            "code": code,
            "ui": {"context_menu": [{"label": "Extract", "handler": name, "item_types": ["FILE"]}]},
        }
    )


class _ScriptedLLM:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._i = 0

    async def chat(
        self,
        messages: list[LLMMessage],
        tools: list[LLMToolDefinition],
        *,
        num_ctx: int,
        response_format: dict[str, Any] | None = None,
    ) -> LLMResponse:
        item = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return LLMResponse(content=item)


class _FakeSkillRepo(AbstractAssistantSkillRepository):
    def __init__(self) -> None:
        self.by_id: dict[UUID, AssistantSkill] = {}
        self.approve_calls: list[UUID] = []

    async def get_by_id(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        skill = self.by_id.get(skill_id)
        return skill if skill and skill.user_id == user_id else None

    async def get_by_name(self, *, user_id: UUID, name: str) -> AssistantSkill | None:
        return next(
            (s for s in self.by_id.values() if s.user_id == user_id and s.name == name), None
        )

    async def list_by_status(
        self, *, user_id: UUID, status: str | None = None
    ) -> list[AssistantSkill]:
        return [
            s
            for s in self.by_id.values()
            if s.user_id == user_id and (status is None or s.status == status)
        ]

    async def create_or_replace_pending(
        self,
        *,
        user_id: UUID,
        name: str,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill:
        now = datetime.now(UTC)
        skill = AssistantSkill(
            id=uuid4(),
            user_id=user_id,
            name=name,
            description=description,
            manifest=manifest,
            code=code,
            status="pending",
            chat_enabled=False,
            created_at=now,
            updated_at=now,
        )
        self.by_id[skill.id] = skill
        return skill

    async def approve(self, *, user_id: UUID, skill_id: UUID) -> AssistantSkill | None:
        self.approve_calls.append(skill_id)
        skill = self.by_id.get(skill_id)
        if skill is None:
            return None
        skill.status = "installed"
        return skill

    async def update(
        self,
        *,
        user_id: UUID,
        skill_id: UUID,
        description: str,
        manifest: dict[str, Any],
        code: str,
    ) -> AssistantSkill | None:
        skill = self.by_id.get(skill_id)
        if skill is None:
            return None
        skill.description = description
        skill.manifest = manifest
        skill.code = code
        return skill

    async def set_chat_enabled(
        self, *, user_id: UUID, skill_id: UUID, enabled: bool
    ) -> AssistantSkill | None:
        skill = self.by_id.get(skill_id)
        if skill is None:
            return None
        skill.chat_enabled = enabled
        return skill

    async def delete(self, *, user_id: UUID, skill_id: UUID) -> bool:
        return self.by_id.pop(skill_id, None) is not None


def _service(
    repo: _FakeSkillRepo, responses: list[str], *, max_repair: int = 2
) -> AssistantSkillService:
    router = ModelRouter(
        local_client=_ScriptedLLM(responses),
        external_client=None,
        external_enabled=False,
        max_local_attempts=1,
        privacy_default="non_sensitive",
    )
    codegen = CodegenSubAgent(
        llm=router, context=ContextManager(num_ctx=4096), num_ctx=4096, max_repair=max_repair
    )
    return AssistantSkillService(
        repo=repo, drive_service=AsyncMock(spec=DriveService), codegen=codegen
    )


async def test_generation_request_stops_at_pending_approval() -> None:
    repo = _FakeSkillRepo()
    service = _service(repo, [_proposal_json()])
    user_id = uuid4()

    result = await service.handle_authoring_message(
        user_id=user_id, message="幫我做一個 7zip 解壓縮功能"
    )

    assert result is not None
    assert result.skill_proposal is not None
    assert result.skill_proposal.name == "decompress_7z"
    assert result.skill_proposal.status == "pending"  # NOT installed
    assert "def run(" in result.skill_proposal.code
    # Persisted as pending, and approve was never called automatically.
    stored = list(repo.by_id.values())
    assert len(stored) == 1 and stored[0].status == "pending"
    assert repo.approve_calls == []


async def test_generation_failure_returns_message_without_proposal() -> None:
    repo = _FakeSkillRepo()
    unsafe = _proposal_json(
        code="import socket\ndef run(input_path, output_dir, params):\n    return {}\n"
    )
    service = _service(repo, [unsafe], max_repair=0)

    result = await service.handle_authoring_message(user_id=uuid4(), message="做一個會連網的功能")

    assert result is not None
    assert result.skill_proposal is None
    assert not repo.by_id  # nothing persisted


async def test_non_authoring_message_returns_none() -> None:
    repo = _FakeSkillRepo()
    service = _service(repo, [_proposal_json()])

    # A normal built-in op must not trigger codegen.
    assert (
        await service.handle_authoring_message(
            user_id=uuid4(), message="把 Demo 這個資料夾改名成 Reports"
        )
        is None
    )
    assert (
        await service.handle_authoring_message(user_id=uuid4(), message="建立一個叫 Demo 的資料夾")
        is None
    )


async def test_generation_disabled_without_codegen() -> None:
    repo = _FakeSkillRepo()
    service = AssistantSkillService(repo=repo, drive_service=AsyncMock(spec=DriveService))

    result = await service.handle_authoring_message(
        user_id=uuid4(), message="幫我做一個 7zip 解壓縮功能"
    )

    assert result is None  # no codegen wired -> not an authoring request
