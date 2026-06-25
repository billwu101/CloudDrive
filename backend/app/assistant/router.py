from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.assistant.context import ContextManager
from app.assistant.hooks import default_hook_registry, snapshot_before_write_hook
from app.assistant.llm.client import (
    ExternalAuthError,
    LLMClient,
    LLMClientError,
    LLMUnavailableError,
)
from app.assistant.llm.external import ExternalLLMClient
from app.assistant.llm.ollama import OllamaLLMClient
from app.assistant.llm.privacy import PrivacyDefault
from app.assistant.llm.router import ModelRouter
from app.assistant.planner import WorkflowPlanner
from app.assistant.repository import (
    AbstractAssistantSessionRepository,
    SQLAssistantSessionRepository,
    SQLAssistantSkillRepository,
    SQLAssistantWorkflowRepository,
)
from app.assistant.schemas import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantMessageResponse,
    AssistantModelOption,
    AssistantSavedWorkflowResponse,
    AssistantSaveWorkflowRequest,
    AssistantSessionResponse,
    AssistantSkillApproveResponse,
    AssistantSkillExecuteRequest,
    AssistantSkillExecuteResponse,
    AssistantSkillResponse,
    AssistantSkillUpdateRequest,
    AssistantWorkflowConfirmResponse,
)
from app.assistant.service import WorkflowService
from app.assistant.skills.authoring import AssistantSkillService
from app.assistant.skills.builtin import build_read_only_registry, register_write_skills
from app.assistant.skills.sandbox import SkillSandbox
from app.assistant.subagent import CodegenSubAgent
from app.assistant.workflow import WorkflowExecutor
from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.repository import SQLDriveItemRepository, SQLUserItemPreferenceRepository
from app.drive.service import DriveService
from app.external_model.factory import build_credential_service
from app.file_version.repository import SQLFileVersionRepository
from app.permission.repository import SQLShareRepository
from app.permission.service import PermissionService
from app.search.factory import build_search_index_service
from app.search.repository import SQLSearchRepository
from app.search.service import SearchService
from app.share.repository import SQLShareLinkRepository
from app.share.service import ShareLinkService
from app.snapshot.repository import SQLSnapshotRepository
from app.snapshot.service import SnapshotService
from app.storage.factory import get_storage_provider
from app.trash.repository import SQLTrashRepository
from app.trash.service import TrashService
from app.upload.service import UploadService
from app.users.repository import SQLUserRepository
from app.users.service import QuotaService

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _drive_service(session: DbSession) -> DriveService:
    activity = ActivityLogService(SQLActivityLogRepository(session))
    return DriveService(
        item_repo=SQLDriveItemRepository(session),
        pref_repo=SQLUserItemPreferenceRepository(session),
        activity_svc=activity,
    )


def _trash_service(session: DbSession) -> TrashService:
    return TrashService(
        item_repo=SQLDriveItemRepository(session),
        trash_repo=SQLTrashRepository(session),
        version_repo=SQLFileVersionRepository(session),
        share_repo=SQLShareRepository(session),
        storage=get_storage_provider(get_settings()),
        quota_svc=QuotaService(SQLUserRepository(session)),
        activity_svc=ActivityLogService(SQLActivityLogRepository(session)),
        snapshot_refs=SQLSnapshotRepository(session),
    )


def _assistant_session_repo(session: DbSession) -> AbstractAssistantSessionRepository:
    return SQLAssistantSessionRepository(session)


def _upload_service(session: DbSession) -> UploadService:
    return UploadService(
        item_repo=SQLDriveItemRepository(session),
        version_repo=SQLFileVersionRepository(session),
        storage=get_storage_provider(get_settings()),
        permission_svc=PermissionService(
            share_repo=SQLShareRepository(session),
            item_repo=SQLDriveItemRepository(session),
        ),
        quota_svc=QuotaService(SQLUserRepository(session)),
        search_indexer=build_search_index_service(session, get_settings()),
    )


def _build_snapshot_service(session: DbSession) -> SnapshotService:
    return SnapshotService(
        repo=SQLSnapshotRepository(session),
        activity=ActivityLogService(SQLActivityLogRepository(session)),
    )


def _assistant_skill_service(session: DbSession) -> AssistantSkillService:
    settings = get_settings()
    return AssistantSkillService(
        repo=SQLAssistantSkillRepository(session),
        drive_service=_drive_service(session),
        sandbox=SkillSandbox(timeout_sec=settings.assistant_sandbox_timeout_sec),
        uploads=_upload_service(session),
        storage=get_storage_provider(settings),
        snapshot_service=_build_snapshot_service(session),
    )


async def _assistant_service(session: DbSession, current_user_id: CurrentUserId) -> WorkflowService:
    settings = get_settings()
    drive_service = _drive_service(session)
    search_service = SearchService(SQLSearchRepository(session))
    quota_service = QuotaService(SQLUserRepository(session))
    registry = build_read_only_registry(
        drive_service=drive_service,
        search_service=search_service,
        quota_service=quota_service,
    )
    register_write_skills(
        registry,
        drive_service=drive_service,
        trash_service=_trash_service(session),
        share_link_service=ShareLinkService(
            item_repo=SQLDriveItemRepository(session),
            link_repo=SQLShareLinkRepository(session),
        ),
    )

    local_client = OllamaLLMClient(
        base_url=settings.llm_base_url,
        model=settings.assistant_model,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.llm_api_key,
        keep_alive=settings.llm_keep_alive,
        fallback_base_urls=(
            [settings.llm_fallback_base_url] if settings.llm_fallback_base_url else []
        ),
    )
    # Global env-configured external client (DEC-023), used when a user has no
    # per-user credential.
    external_client: ExternalLLMClient | LLMClient | None = None
    if settings.external_llm_enabled and settings.external_llm_base_url and settings.external_model:
        external_client = ExternalLLMClient(
            base_url=settings.external_llm_base_url,
            model=settings.external_model,
            api_key=settings.external_llm_api_key,
        )
    # Per-user credential (DEC-026) takes precedence over the global client.
    credential_service = build_credential_service(session, settings)
    per_user_external = await credential_service.build_chat_client(current_user_id)
    if per_user_external is not None:
        external_client = per_user_external
    # Per-provider clients for explicit model selection (no codex→openai chaining).
    external_clients = await credential_service.build_provider_clients(current_user_id)

    privacy_default = cast(
        PrivacyDefault,
        settings.privacy_default
        if settings.privacy_default in {"sensitive", "non_sensitive"}
        else "sensitive",
    )
    model_router = ModelRouter(
        local_client=local_client,
        external_client=external_client,
        # Enabled whenever an external client exists — a per-user credential is
        # itself the user's explicit opt-in; the global client already gated on
        # external_llm_enabled when constructed.
        external_enabled=external_client is not None,
        max_local_attempts=settings.max_local_attempts,
        privacy_default=privacy_default,
        external_clients=external_clients,
    )
    context = ContextManager(num_ctx=settings.llm_num_ctx)
    planner = WorkflowPlanner(
        llm=model_router,
        registry=registry,
        context=context,
        num_ctx=settings.llm_num_ctx,
    )
    hooks = default_hook_registry()
    hooks.register(
        "before_execution",
        snapshot_before_write_hook(_build_snapshot_service(session)),
    )
    executor = WorkflowExecutor(registry=registry, hooks=hooks)
    codegen = CodegenSubAgent(llm=model_router, context=context, num_ctx=settings.llm_num_ctx)
    return WorkflowService(
        planner=planner,
        executor=executor,
        registry=registry,
        workflow_repo=SQLAssistantWorkflowRepository(session),
        skill_authoring=AssistantSkillService(
            repo=SQLAssistantSkillRepository(session),
            drive_service=drive_service,
            codegen=codegen,
            snapshot_service=_build_snapshot_service(session),
        ),
    )


AssistantServiceDep = Annotated[WorkflowService, Depends(_assistant_service)]
AssistantSkillServiceDep = Annotated[AssistantSkillService, Depends(_assistant_skill_service)]
AssistantSessionRepoDep = Annotated[
    AbstractAssistantSessionRepository, Depends(_assistant_session_repo)
]


# Human-readable labels for selectable models, shared by the picker and errors.
_MODEL_LABELS = {
    "local": "the local model",
    "openai": "OpenAI",
    "codex": "the Codex subscription",
}


@router.get(
    "/models",
    response_model=list[AssistantModelOption],
    summary="List models the user can pick for the assistant",
)
async def list_models(
    current_user_id: CurrentUserId,
    session: DbSession,
) -> list[AssistantModelOption]:
    settings = get_settings()
    providers = await build_credential_service(session, settings).active_providers(current_user_id)
    return [
        AssistantModelOption(
            id="local", label=f"Local ({settings.assistant_model})", available=True
        ),
        AssistantModelOption(id="openai", label="OpenAI", available="openai" in providers),
        AssistantModelOption(
            id="codex", label="Codex subscription", available="codex" in providers
        ),
    ]


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Chat with the in-app assistant",
    responses={503: {"description": "Assistant unavailable"}},
)
async def chat(
    body: AssistantChatRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantServiceDep,
    session_repo: AssistantSessionRepoDep,
) -> AssistantChatResponse:
    settings = get_settings()
    if not settings.assistant_enabled:
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            "Assistant is disabled",
            status_code=503,
        )
    label = _MODEL_LABELS.get(body.model or "", "the assistant model")
    try:
        response = await service.chat(
            user_id=current_user_id,
            session_id=body.session_id,
            message=body.message,
            target=body.model,
        )
    except ExternalAuthError as exc:
        # The provider rejected the credential itself (invalid key / quota).
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            f"The credential for {label} was rejected — it may be invalid or out of quota. "
            "Update it in Settings or pick another model.",
            status_code=503,
        ) from exc
    except LLMUnavailableError as exc:
        # The selected model could not be reached (offline / not configured).
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            f"Could not connect to {label}. It may be offline or not configured — "
            "pick another model or try again later.",
            status_code=503,
        ) from exc
    except LLMClientError as exc:
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            f"{label} returned an unexpected error. Pick another model or try again.",
            status_code=503,
        ) from exc
    # Persist the conversation turn so the session can be resumed later.
    await session_repo.ensure_session(
        user_id=current_user_id,
        session_id=response.session_id,
        title=body.message,
    )
    await session_repo.add_message(
        session_id=response.session_id, role="user", content=body.message
    )
    await session_repo.add_message(
        session_id=response.session_id,
        role="assistant",
        content=response.message,
        tool_calls=[tc.model_dump(mode="json") for tc in response.tool_calls],
    )
    # Persist skill proposals, fast-path runs, and pending workflows.
    await session.commit()
    return response


@router.get(
    "/sessions",
    response_model=list[AssistantSessionResponse],
    summary="List the user's assistant conversations",
)
async def list_sessions(
    current_user_id: CurrentUserId,
    session_repo: AssistantSessionRepoDep,
) -> list[AssistantSessionResponse]:
    sessions = await session_repo.list_sessions(user_id=current_user_id)
    return [AssistantSessionResponse.model_validate(s) for s in sessions]


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[AssistantMessageResponse],
    summary="Get the message history for a conversation",
)
async def list_session_messages(
    session_id: UUID,
    current_user_id: CurrentUserId,
    session_repo: AssistantSessionRepoDep,
) -> list[AssistantMessageResponse]:
    messages = await session_repo.list_messages(user_id=current_user_id, session_id=session_id)
    return [AssistantMessageResponse.model_validate(m) for m in messages]


@router.post(
    "/workflows/{workflow_id}/confirm",
    response_model=AssistantWorkflowConfirmResponse,
    summary="Confirm and execute a pending workflow",
)
async def confirm_workflow(
    workflow_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantServiceDep,
) -> AssistantWorkflowConfirmResponse:
    response = await service.confirm(user_id=current_user_id, workflow_id=workflow_id)
    await session.commit()
    return response


@router.post(
    "/workflows/{workflow_id}/cancel",
    response_model=AssistantWorkflowConfirmResponse,
    summary="Cancel a pending workflow",
)
async def cancel_workflow(
    workflow_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantServiceDep,
) -> AssistantWorkflowConfirmResponse:
    response = await service.cancel(user_id=current_user_id, workflow_id=workflow_id)
    await session.commit()
    return response


@router.post(
    "/workflows/save",
    response_model=AssistantSavedWorkflowResponse,
    summary="Save a workflow under a name for later reuse",
)
async def save_workflow(
    body: AssistantSaveWorkflowRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantServiceDep,
) -> AssistantSavedWorkflowResponse:
    workflow = await service.save_workflow(
        user_id=current_user_id,
        name=body.name,
        source_nl=body.source_nl,
        steps=body.steps,
    )
    await session.commit()
    return AssistantSavedWorkflowResponse.model_validate(workflow)


@router.get(
    "/workflows/saved",
    response_model=list[AssistantSavedWorkflowResponse],
    summary="List the user's saved workflows",
)
async def list_saved_workflows(
    current_user_id: CurrentUserId,
    service: AssistantServiceDep,
) -> list[AssistantSavedWorkflowResponse]:
    workflows = await service.list_saved_workflows(user_id=current_user_id)
    return [AssistantSavedWorkflowResponse.model_validate(w) for w in workflows]


@router.post(
    "/workflows/saved/{workflow_id}/rerun",
    response_model=AssistantWorkflowConfirmResponse,
    summary="Re-execute a saved workflow",
)
async def rerun_workflow(
    workflow_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantServiceDep,
) -> AssistantWorkflowConfirmResponse:
    response = await service.rerun_workflow(user_id=current_user_id, workflow_id=workflow_id)
    await session.commit()
    return response


@router.get(
    "/skills",
    response_model=list[AssistantSkillResponse],
    summary="List assistant skills",
)
async def list_skills(
    current_user_id: CurrentUserId,
    service: AssistantSkillServiceDep,
    status: str | None = "installed",
) -> list[AssistantSkillResponse]:
    return await service.list_skills(user_id=current_user_id, status=status)


@router.post(
    "/skills/{skill_id}/approve",
    response_model=AssistantSkillApproveResponse,
    summary="Approve and install an assistant skill manifest",
)
async def approve_skill(
    skill_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantSkillServiceDep,
) -> AssistantSkillApproveResponse:
    skill = await service.approve_skill(user_id=current_user_id, skill_id=skill_id)
    await session.commit()
    return AssistantSkillApproveResponse(
        skill=skill,
        message=f"{skill.manifest['name']} installed.",
    )


@router.patch(
    "/skills/{skill_id}",
    response_model=AssistantSkillResponse,
    summary="Edit an assistant skill's description and/or code",
)
async def update_skill(
    skill_id: UUID,
    body: AssistantSkillUpdateRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantSkillServiceDep,
) -> AssistantSkillResponse:
    skill = await service.update_skill(
        user_id=current_user_id,
        skill_id=skill_id,
        description=body.description,
        code=body.code,
    )
    await session.commit()
    return skill


@router.delete(
    "/skills/{skill_id}",
    status_code=204,
    summary="Delete an assistant skill",
)
async def delete_skill(
    skill_id: UUID,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantSkillServiceDep,
) -> None:
    await service.delete_skill(user_id=current_user_id, skill_id=skill_id)
    await session.commit()


@router.post(
    "/skills/{skill_id}/execute",
    response_model=AssistantSkillExecuteResponse,
    summary="Execute an installed assistant skill",
)
async def execute_skill(
    skill_id: UUID,
    body: AssistantSkillExecuteRequest,
    current_user_id: CurrentUserId,
    session: DbSession,
    service: AssistantSkillServiceDep,
) -> AssistantSkillExecuteResponse:
    response = await service.execute_skill(
        user_id=current_user_id,
        skill_id=skill_id,
        item_id=body.item_id,
    )
    # Generated skills ingest produced files as new drive items — persist them.
    await session.commit()
    return response
