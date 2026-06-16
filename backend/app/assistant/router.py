from __future__ import annotations

from typing import Annotated, cast

from fastapi import APIRouter, Depends

from app.activity_log.repository import SQLActivityLogRepository
from app.activity_log.service import ActivityLogService
from app.assistant.context import ContextManager
from app.assistant.llm.client import LLMClientError
from app.assistant.llm.external import ExternalLLMClient
from app.assistant.llm.ollama import OllamaLLMClient
from app.assistant.llm.privacy import PrivacyDefault
from app.assistant.llm.router import ModelRouter
from app.assistant.schemas import AssistantChatRequest, AssistantChatResponse
from app.assistant.service import AgentService
from app.assistant.skills.builtin import build_read_only_registry
from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError
from app.drive.repository import SQLDriveItemRepository, SQLUserItemPreferenceRepository
from app.drive.service import DriveService
from app.search.repository import SQLSearchRepository
from app.search.service import SearchService
from app.users.repository import SQLUserRepository
from app.users.service import QuotaService

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _assistant_service(session: DbSession) -> AgentService:
    settings = get_settings()
    activity = ActivityLogService(SQLActivityLogRepository(session))
    drive_service = DriveService(
        item_repo=SQLDriveItemRepository(session),
        pref_repo=SQLUserItemPreferenceRepository(session),
        activity_svc=activity,
    )
    search_service = SearchService(SQLSearchRepository(session))
    quota_service = QuotaService(SQLUserRepository(session))
    registry = build_read_only_registry(
        drive_service=drive_service,
        search_service=search_service,
        quota_service=quota_service,
    )

    local_client = OllamaLLMClient(
        base_url=settings.llm_base_url,
        model=settings.assistant_model,
        timeout=settings.llm_timeout_seconds,
        api_key=settings.llm_api_key,
        keep_alive=settings.llm_keep_alive,
    )
    external_client = None
    if settings.external_llm_enabled and settings.external_llm_base_url and settings.external_model:
        external_client = ExternalLLMClient(
            base_url=settings.external_llm_base_url,
            model=settings.external_model,
            api_key=settings.external_llm_api_key,
        )
    privacy_default = cast(
        PrivacyDefault,
        settings.privacy_default
        if settings.privacy_default in {"sensitive", "non_sensitive"}
        else "sensitive",
    )
    model_router = ModelRouter(
        local_client=local_client,
        external_client=external_client,
        external_enabled=settings.external_llm_enabled,
        max_local_attempts=settings.max_local_attempts,
        privacy_default=privacy_default,
    )
    return AgentService(
        llm=model_router,
        registry=registry,
        context=ContextManager(num_ctx=settings.llm_num_ctx),
        max_tool_iterations=settings.assistant_max_tool_iterations,
        num_ctx=settings.llm_num_ctx,
    )


AssistantServiceDep = Annotated[AgentService, Depends(_assistant_service)]


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Chat with the in-app assistant",
    responses={503: {"description": "Assistant unavailable"}},
)
async def chat(
    body: AssistantChatRequest,
    current_user_id: CurrentUserId,
    service: AssistantServiceDep,
) -> AssistantChatResponse:
    settings = get_settings()
    if not settings.assistant_enabled:
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            "Assistant is disabled",
            status_code=503,
        )
    try:
        return await service.chat(
            user_id=current_user_id,
            session_id=body.session_id,
            message=body.message,
        )
    except LLMClientError as exc:
        raise AppError(
            ErrorCode.ASSISTANT_UNAVAILABLE,
            "Assistant model is unavailable",
            status_code=503,
        ) from exc
