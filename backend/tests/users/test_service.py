from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import AppError, NotFoundError, QuotaExceededError
from app.core.security import hash_password, verify_password
from app.models.user import User
from app.users.repository import AbstractUserRepository
from app.users.service import QuotaService, UserService


def _user(
    *,
    quota_bytes: int = 10 * 1024 * 1024,
    used_bytes: int = 0,
    is_active: bool = True,
) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="test@example.com",
        username="testuser",
        password_hash="hash",
        avatar_url=None,
        quota_bytes=quota_bytes,
        used_bytes=used_bytes,
        is_active=is_active,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


class MockUserRepo(AbstractUserRepository):
    def __init__(self, user: User | None = None) -> None:
        self._user = user
        self._add_delta = 0
        self._subtract_delta = 0
        self._recalc_result = 0
        self._email_conflicts: dict[str, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        if self._user and self._user.id == user_id:
            return self._user
        return None

    async def get_by_email(self, email: str) -> User | None:
        if email in self._email_conflicts:
            return self._email_conflicts[email]
        if self._user and self._user.email == email:
            return self._user
        return None

    async def update_username(self, user_id: UUID, username: str) -> User:
        assert self._user is not None
        self._user.username = username
        return self._user

    async def update_email(self, user_id: UUID, email: str) -> User:
        assert self._user is not None
        self._user.email = email
        return self._user

    async def update_password(self, user_id: UUID, password_hash: str) -> User:
        assert self._user is not None
        self._user.password_hash = password_hash
        return self._user

    async def add_used_bytes(self, user_id: UUID, delta: int) -> None:
        assert self._user is not None
        self._user.used_bytes += delta
        self._add_delta += delta

    async def subtract_used_bytes(self, user_id: UUID, delta: int) -> None:
        assert self._user is not None
        self._user.used_bytes = max(0, self._user.used_bytes - delta)
        self._subtract_delta += delta

    async def recalculate_used_bytes(self, user_id: UUID) -> int:
        assert self._user is not None
        self._user.used_bytes = self._recalc_result
        return self._recalc_result


class TestUserService:
    async def test_get_by_id_returns_user(self) -> None:
        u = _user()
        svc = UserService(MockUserRepo(u))
        result = await svc.get_by_id(u.id)
        assert result.id == u.id

    async def test_get_by_id_missing_raises(self) -> None:
        svc = UserService(MockUserRepo())
        with pytest.raises(NotFoundError):
            await svc.get_by_id(uuid4())

    async def test_get_by_email_returns_user(self) -> None:
        u = _user()
        svc = UserService(MockUserRepo(u))
        result = await svc.get_by_email(u.email)
        assert result.email == u.email

    async def test_get_by_email_missing_raises(self) -> None:
        svc = UserService(MockUserRepo())
        with pytest.raises(NotFoundError):
            await svc.get_by_email("nobody@example.com")

    async def test_update_username(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        svc = UserService(repo)
        result = await svc.update_username(u.id, "newname")
        assert result.username == "newname"

    async def test_update_username_strips_whitespace(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        svc = UserService(repo)
        result = await svc.update_username(u.id, "  trimmed  ")
        assert result.username == "trimmed"

    async def test_update_email_success(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        svc = UserService(repo)
        result = await svc.update_email(u.id, "new@example.com")
        assert result.email == "new@example.com"

    async def test_update_email_normalizes_value(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        svc = UserService(repo)
        result = await svc.update_email(u.id, "  New@Example.COM  ")
        assert result.email == "new@example.com"

    async def test_update_email_conflict_raises(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        other = _user()
        repo._email_conflicts["taken@example.com"] = other
        svc = UserService(repo)
        with pytest.raises(AppError) as exc_info:
            await svc.update_email(u.id, "taken@example.com")
        assert exc_info.value.status_code == 409

    async def test_update_email_same_user_no_conflict(self) -> None:
        u = _user()
        repo = MockUserRepo(u)
        svc = UserService(repo)
        result = await svc.update_email(u.id, u.email)
        assert result.email == u.email

    async def test_change_password_success(self) -> None:
        u = _user()
        u.password_hash = hash_password("correct_password")
        repo = MockUserRepo(u)
        svc = UserService(repo)
        await svc.change_password(u.id, "correct_password", "new_secure_password")
        assert verify_password("new_secure_password", u.password_hash)
        assert not verify_password("correct_password", u.password_hash)

    async def test_change_password_wrong_current_raises(self) -> None:
        u = _user()
        u.password_hash = hash_password("correct_password")
        repo = MockUserRepo(u)
        svc = UserService(repo)
        with pytest.raises(AppError) as exc_info:
            await svc.change_password(u.id, "wrong_password", "new_secure_password")
        assert exc_info.value.status_code == 400


class TestQuotaService:
    async def test_get_quota_info(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=250)
        svc = QuotaService(MockUserRepo(u))
        info = await svc.get_quota_info(u.id)
        assert info.quota_bytes == 1000
        assert info.used_bytes == 250
        assert info.available_bytes == 750
        assert info.used_percent == 25.0

    async def test_assert_has_space_passes(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=500)
        svc = QuotaService(MockUserRepo(u))
        await svc.assert_has_space(u.id, 499)

    async def test_assert_has_space_fails(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=900)
        svc = QuotaService(MockUserRepo(u))
        with pytest.raises(QuotaExceededError):
            await svc.assert_has_space(u.id, 200)

    async def test_add_used_bytes(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=0)
        repo = MockUserRepo(u)
        svc = QuotaService(repo)
        await svc.add_used_bytes(u.id, 300)
        assert u.used_bytes == 300

    async def test_subtract_used_bytes(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=500)
        repo = MockUserRepo(u)
        svc = QuotaService(repo)
        await svc.subtract_used_bytes(u.id, 200)
        assert u.used_bytes == 300

    async def test_subtract_used_bytes_no_negative(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=100)
        repo = MockUserRepo(u)
        svc = QuotaService(repo)
        await svc.subtract_used_bytes(u.id, 999)
        assert u.used_bytes == 0

    async def test_recalculate_used_bytes(self) -> None:
        u = _user(quota_bytes=1000, used_bytes=999)
        repo = MockUserRepo(u)
        repo._recalc_result = 450
        svc = QuotaService(repo)
        total = await svc.recalculate_used_bytes(u.id)
        assert total == 450
        assert u.used_bytes == 450

    async def test_folder_does_not_count_quota(self) -> None:
        u = _user(quota_bytes=100, used_bytes=0)
        svc = QuotaService(MockUserRepo(u))
        await svc.assert_has_space(u.id, 0)
