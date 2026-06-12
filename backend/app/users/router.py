from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import CurrentUserId, DbSession
from app.schemas.common import CurrentUserResponse
from app.users.repository import SQLUserRepository
from app.users.schemas import QuotaResponse, UpdateProfileRequest
from app.users.service import QuotaService, UserService

router = APIRouter(prefix="/users", tags=["users"])


def _user_service(session: DbSession) -> UserService:
    return UserService(repo=SQLUserRepository(session))


def _quota_service(session: DbSession) -> QuotaService:
    return QuotaService(repo=SQLUserRepository(session))


UserServiceDep = Annotated[UserService, Depends(_user_service)]
QuotaServiceDep = Annotated[QuotaService, Depends(_quota_service)]


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current user profile",
)
async def get_me(
    current_user_id: CurrentUserId,
    service: UserServiceDep,
) -> CurrentUserResponse:
    user = await service.get_by_id(current_user_id)
    return CurrentUserResponse.model_validate(user)


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    summary="Update current user profile",
)
async def update_me(
    body: UpdateProfileRequest,
    current_user_id: CurrentUserId,
    service: UserServiceDep,
    session: DbSession,
) -> CurrentUserResponse:
    user = await service.update_username(current_user_id, body.username)
    await session.commit()
    return CurrentUserResponse.model_validate(user)


@router.get(
    "/me/quota",
    response_model=QuotaResponse,
    summary="Get current user storage quota",
)
async def get_my_quota(
    current_user_id: CurrentUserId,
    service: QuotaServiceDep,
) -> QuotaResponse:
    return await service.get_quota_info(current_user_id)
