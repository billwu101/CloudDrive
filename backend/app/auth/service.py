from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.auth.repository import (
    AbstractRefreshTokenRepository,
    AbstractUserRepository,
    hash_token,
)
from app.core.config import get_settings
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    generate_random_password,
    hash_password,
    verify_password,
)
from app.email.base import EmailProvider
from app.models.user import User

RESET_PASSWORD_LENGTH = 10


class AuthService:
    def __init__(
        self,
        user_repo: AbstractUserRepository,
        refresh_token_repo: AbstractRefreshTokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._rt_repo = refresh_token_repo

    async def register(self, *, email: str, username: str, password: str) -> User:
        existing = await self._user_repo.get_by_email(email)
        if existing is not None:
            raise AppError(
                ErrorCode.EMAIL_ALREADY_EXISTS,
                "Email already registered",
                status_code=409,
            )
        pw_hash = hash_password(password)
        settings = get_settings()
        return await self._user_repo.create(
            email=email,
            username=username,
            password_hash=pw_hash,
            quota_bytes=settings.default_user_quota_bytes,
        )

    async def login(self, *, email: str, password: str) -> tuple[User, str, str]:
        user = await self._user_repo.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            raise AppError(
                ErrorCode.INVALID_CREDENTIALS,
                "Invalid credentials",
                status_code=401,
            )
        if not user.is_active:
            raise AppError(
                ErrorCode.USER_INACTIVE,
                "Account is disabled",
                status_code=403,
            )
        access_token = create_access_token(user.id)
        refresh_token_str, rt_hash, expires_at = self._issue_refresh_token(user.id)
        await self._rt_repo.create(
            user_id=user.id,
            token_hash=rt_hash,
            expires_at=expires_at,
        )
        return user, access_token, refresh_token_str

    async def refresh(self, *, refresh_token_str: str) -> tuple[User, str, str]:
        try:
            user_id = decode_refresh_token(refresh_token_str)
        except AppError as exc:
            raise AppError(
                ErrorCode.UNAUTHORIZED,
                "Invalid refresh token",
                status_code=401,
            ) from exc

        rt_hash = hash_token(refresh_token_str)
        rt = await self._rt_repo.get_by_hash(rt_hash)
        if rt is None or rt.revoked_at is not None:
            raise AppError(
                ErrorCode.REFRESH_TOKEN_REVOKED,
                "Refresh token has been revoked",
                status_code=401,
            )
        if rt.expires_at <= datetime.now(UTC):
            raise AppError(
                ErrorCode.UNAUTHORIZED,
                "Refresh token has expired",
                status_code=401,
            )

        await self._rt_repo.revoke(rt.id)

        user = await self._user_repo.get_by_id(user_id)
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        access_token = create_access_token(user.id)
        new_rt_str, new_rt_hash, new_expires_at = self._issue_refresh_token(user.id)
        await self._rt_repo.create(
            user_id=user.id,
            token_hash=new_rt_hash,
            expires_at=new_expires_at,
        )
        return user, access_token, new_rt_str

    async def forgot_password(self, *, email: str, email_provider: EmailProvider) -> None:
        """Reset the user's password to a random one and email it to them.

        Non-enumerable: returns normally whether or not the email maps to a
        real account, so callers cannot probe which addresses are registered.
        """
        normalized_email = email.strip().lower()
        user = await self._user_repo.get_by_email(normalized_email)
        if user is None or not user.is_active:
            return

        new_password = generate_random_password(RESET_PASSWORD_LENGTH)
        await self._user_repo.reset_password(user.id, hash_password(new_password))

        subject = "Your Cloud Drive password has been reset"
        body = (
            f"Hi {user.username},\n\n"
            "You requested a password reset for your Cloud Drive account.\n"
            f"Your temporary password is:\n\n    {new_password}\n\n"
            "Sign in with this password, then change it immediately from "
            "Account Settings. For your security, you will be reminded to "
            "update it after logging in.\n\n"
            "If you did not request this, please secure your email account.\n\n"
            "— Cloud Drive"
        )
        await email_provider.send(to=user.email, subject=subject, body=body)

    async def logout(self, *, refresh_token_str: str) -> None:
        rt_hash = hash_token(refresh_token_str)
        rt = await self._rt_repo.get_by_hash(rt_hash)
        if rt is not None and rt.revoked_at is None:
            await self._rt_repo.revoke(rt.id)

    async def get_current_user(self, user_id: UUID) -> User:
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise UnauthorizedError("User not found")
        return user

    def _issue_refresh_token(self, user_id: UUID) -> tuple[str, str, datetime]:
        settings = get_settings()
        token_str = create_refresh_token(user_id)
        token_hash = hash_token(token_str)
        expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        return token_str, token_hash, expires_at
