from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.assistant.workflow import PlannedStep, StepResult, WorkflowStep

AssistantRole = Literal["system", "user", "assistant", "tool"]
WorkflowPlanStatus = Literal["auto_executed", "pending_approval"]


# Which model the user picked for this turn: "local" = on-prem Ollama, or a
# connection id (str) for one of the user's named external connections. None =
# server default (local→external fallback). Validated against availability.
class AssistantChatRequest(BaseModel):
    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=4000)
    model: str | None = None
    # Drive items the user checked; self-built skills run once per selected file
    # (their item_id comes from here, never guessed by the LLM).
    selected_item_ids: list[UUID] = Field(default_factory=list)


class AssistantModelOption(BaseModel):
    """One selectable model in the assistant's picker."""

    id: str  # "local" | "openai" | "codex"
    label: str
    available: bool


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
    chat_enabled: bool
    created_at: datetime
    updated_at: datetime


class AssistantSkillApproveResponse(BaseModel):
    skill: AssistantSkillResponse
    message: str


class AssistantSkillUpdateRequest(BaseModel):
    description: str | None = Field(default=None, min_length=1, max_length=500)
    code: str | None = Field(default=None, max_length=20000)
    # Opt the installed skill in/out of the chat planner (None = leave unchanged).
    chat_enabled: bool | None = None


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


class AssistantSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class AssistantMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class AssistantWorkflowConfirmResponse(BaseModel):
    workflow_id: UUID
    status: Literal["executed", "cancelled"]
    message: str
    results: list[StepResult] = Field(default_factory=list)


class AssistantSaveWorkflowRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    source_nl: str = Field(default="", max_length=4000)
    steps: list[PlannedStep] = Field(min_length=1)


class AssistantSavedWorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_nl: str
    steps: list[WorkflowStep]
    created_at: datetime
