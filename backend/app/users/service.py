from __future__ import annotations

from uuid import UUID

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, NotFoundError, QuotaExceededError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.users.repository import AbstractUserRepository
from app.users.schemas import QuotaResponse


class UserService:
    def __init__(self, repo: AbstractUserRepository) -> None:
        self._repo = repo

    async def get_by_id(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def get_by_email(self, email: str) -> User:
        user = await self._repo.get_by_email(email)
        if user is None:
            raise NotFoundError("User not found")
        return user

    async def update_username(self, user_id: UUID, username: str) -> User:
        await self.get_by_id(user_id)
        return await self._repo.update_username(user_id, username.strip())

    async def update_email(self, user_id: UUID, email: str) -> User:
        await self.get_by_id(user_id)
        normalized_email = email.strip().lower()
        existing = await self._repo.get_by_email(normalized_email)
        if existing is not None and existing.id != user_id:
            raise AppError(ErrorCode.EMAIL_ALREADY_EXISTS, "Email already in use", status_code=409)
        return await self._repo.update_email(user_id, normalized_email)

    async def change_password(
        self, user_id: UUID, current_password: str, new_password: str
    ) -> None:
        user = await self.get_by_id(user_id)
        if not verify_password(current_password, user.password_hash):
            raise AppError(
                ErrorCode.INVALID_CREDENTIALS,
                "Current password is incorrect",
                status_code=400,
            )
        await self._repo.update_password(user_id, hash_password(new_password))


class QuotaService:
    def __init__(self, repo: AbstractUserRepository) -> None:
        self._repo = repo

    async def get_quota_info(self, user_id: UUID) -> QuotaResponse:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        available = max(0, user.quota_bytes - user.used_bytes)
        used_percent = (user.used_bytes / user.quota_bytes * 100.0) if user.quota_bytes > 0 else 0.0
        return QuotaResponse(
            quota_bytes=user.quota_bytes,
            used_bytes=user.used_bytes,
            available_bytes=available,
            used_percent=round(used_percent, 2),
        )

    async def assert_has_space(self, user_id: UUID, bytes_needed: int) -> None:
        user = await self._repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        available = user.quota_bytes - user.used_bytes
        if available < bytes_needed:
            raise QuotaExceededError(
                f"Insufficient storage space: need {bytes_needed}, available {available}"
            )

    async def add_used_bytes(self, user_id: UUID, delta: int) -> None:
        if delta < 0:
            raise AppError(ErrorCode.INVALID_OPERATION, "delta must be non-negative")
        await self._repo.add_used_bytes(user_id, delta)

    async def subtract_used_bytes(self, user_id: UUID, delta: int) -> None:
        if delta < 0:
            raise AppError(ErrorCode.INVALID_OPERATION, "delta must be non-negative")
        await self._repo.subtract_used_bytes(user_id, delta)

    async def recalculate_used_bytes(self, user_id: UUID) -> int:
        return await self._repo.recalculate_used_bytes(user_id)
