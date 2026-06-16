from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.assistant.workflow import StepResult, WorkflowStep

AssistantRole = Literal["system", "user", "assistant", "tool"]
WorkflowPlanStatus = Literal["auto_executed", "pending_approval"]


class AssistantChatRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)


class AssistantToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class AssistantToolResult(BaseModel):
    name: str
    ok: bool
    output: Any | None = None
    error: str | None = None


class AssistantSkillContextMenuAction(BaseModel):
    label: str
    handler: str
    item_types: list[str] = Field(default_factory=lambda: ["FILE", "FOLDER"])


class AssistantSkillUI(BaseModel):
    context_menu: list[AssistantSkillContextMenuAction] = Field(default_factory=list)


class AssistantSkillManifest(BaseModel):
    name: str
    description: str
    version: str = "1.0.0"
    ui: AssistantSkillUI


class AssistantSkillResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    manifest: dict[str, Any]
    code: str
    status: str
    created_at: datetime
    updated_at: datetime


class AssistantSkillApproveResponse(BaseModel):
    skill: AssistantSkillResponse
    message: str


class AssistantSkillExecuteRequest(BaseModel):
    item_id: UUID


class AssistantSkillExecuteResponse(BaseModel):
    skill_id: UUID
    skill_name: str
    item_id: UUID
    message: str
    output: dict[str, Any]


class WorkflowPlanView(BaseModel):
    workflow_id: UUID | None = None
    status: WorkflowPlanStatus
    steps: list[WorkflowStep]


class AssistantChatResponse(BaseModel):
    session_id: UUID
    message: str
    tool_calls: list[AssistantToolCall] = Field(default_factory=list)
    tool_results: list[AssistantToolResult] = Field(default_factory=list)
    plan: WorkflowPlanView | None = None
    results: list[StepResult] = Field(default_factory=list)
    skill_proposal: AssistantSkillResponse | None = None


class AssistantWorkflowConfirmResponse(BaseModel):
    workflow_id: UUID
    status: Literal["executed", "cancelled"]
    message: str
    results: list[StepResult] = Field(default_factory=list)
