from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response

from app.auth.repository import SQLRefreshTokenRepository, SQLUserRepository
from app.auth.schemas import LoginRequest, RegisterRequest
from app.auth.service import AuthService
from app.core.config import get_settings
from app.core.dependencies import CurrentUserId, DbSession
from app.core.exceptions import UnauthorizedError
from app.schemas.common import CurrentUserResponse, TokenPairResponse

router = APIRouter(prefix="/auth", tags=["auth"])


def _make_service(session: DbSession) -> AuthService:
    return AuthService(
        user_repo=SQLUserRepository(session),
        refresh_token_repo=SQLRefreshTokenRepository(session),
    )


AuthServiceDep = Annotated[AuthService, Depends(_make_service)]

RefreshTokenCookie = Annotated[str | None, Cookie(alias="refresh_token")]


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    secure = settings.app_env != "test"
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/api/v1/auth",
    )


@router.post(
    "/register",
    response_model=CurrentUserResponse,
    status_code=201,
    summary="Register a new user",
    responses={409: {"description": "Email already registered"}},
)
async def register(
    body: RegisterRequest,
    service: AuthServiceDep,
    session: DbSession,
) -> CurrentUserResponse:
    user = await service.register(
        email=body.email,
        username=body.username,
        password=body.password,
    )
    await session.commit()
    return CurrentUserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPairResponse,
    summary="Authenticate and receive access token",
    responses={
        401: {"description": "Invalid credentials"},
        403: {"description": "Account disabled"},
    },
)
async def login(
    body: LoginRequest,
    response: Response,
    service: AuthServiceDep,
    session: DbSession,
) -> TokenPairResponse:
    _, access_token, refresh_token = await service.login(
        email=body.email,
        password=body.password,
    )
    await session.commit()
    _set_refresh_cookie(response, refresh_token)
    return TokenPairResponse(access_token=access_token)


@router.post(
    "/refresh",
    response_model=TokenPairResponse,
    summary="Rotate refresh token and obtain new access token",
    responses={401: {"description": "Invalid or revoked refresh token"}},
)
async def refresh(
    response: Response,
    service: AuthServiceDep,
    session: DbSession,
    refresh_token: RefreshTokenCookie = None,
) -> TokenPairResponse:
    if refresh_token is None:
        raise UnauthorizedError("No refresh token provided")
    _, access_token, new_refresh_token = await service.refresh(
        refresh_token_str=refresh_token,
    )
    await session.commit()
    _set_refresh_cookie(response, new_refresh_token)
    return TokenPairResponse(access_token=access_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Revoke refresh token and clear cookie",
)
async def logout(
    response: Response,
    service: AuthServiceDep,
    session: DbSession,
    refresh_token: RefreshTokenCookie = None,
) -> None:
    if refresh_token is not None:
        await service.logout(refresh_token_str=refresh_token)
        await session.commit()
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    summary="Get current authenticated user",
    responses={401: {"description": "Not authenticated"}},
)
async def me(
    current_user_id: CurrentUserId,
    service: AuthServiceDep,
) -> CurrentUserResponse:
    user = await service.get_current_user(current_user_id)
    return CurrentUserResponse.model_validate(user)
