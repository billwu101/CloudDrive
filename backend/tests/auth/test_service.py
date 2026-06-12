from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.auth.repository import (
    AbstractRefreshTokenRepository,
    AbstractUserRepository,
    hash_token,
)
from app.auth.service import AuthService
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, UnauthorizedError
from app.core.security import create_refresh_token, hash_password
from app.models.refresh_token import RefreshToken
from app.models.user import User


def _make_user(
    *,
    email: str = "user@example.com",
    password: str = "password123",
    is_active: bool = True,
) -> User:
    now = datetime.now(UTC)
    uid = uuid4()
    return User(
        id=uid,
        email=email,
        username="testuser",
        password_hash=hash_password(password),
        avatar_url=None,
        quota_bytes=15 * 1024 * 1024 * 1024,
        used_bytes=0,
        is_active=is_active,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _make_rt(user: User, *, token_str: str, revoked: bool = False) -> RefreshToken:
    now = datetime.now(UTC)
    return RefreshToken(
        id=uuid4(),
        user_id=user.id,
        token_hash=hash_token(token_str),
        expires_at=now + timedelta(days=30),
        revoked_at=now if revoked else None,
        created_at=now,
    )


class MockUserRepo(AbstractUserRepository):
    def __init__(self, users: list[User] | None = None) -> None:
        self._users: list[User] = users or []
        self.created: list[User] = []

    async def get_by_email(self, email: str) -> User | None:
        return next((u for u in self._users if u.email == email), None)

    async def get_by_id(self, user_id: object) -> User | None:
        return next((u for u in self._users if u.id == user_id), None)

    async def create(
        self,
        *,
        email: str,
        username: str,
        password_hash: str,
        quota_bytes: int,
    ) -> User:
        now = datetime.now(UTC)
        user = User(
            id=uuid4(),
            email=email,
            username=username,
            password_hash=password_hash,
            avatar_url=None,
            quota_bytes=quota_bytes,
            used_bytes=0,
            is_active=True,
            is_admin=False,
            created_at=now,
            updated_at=now,
        )
        self._users.append(user)
        self.created.append(user)
        return user


class MockRefreshTokenRepo(AbstractRefreshTokenRepository):
    def __init__(self, tokens: list[RefreshToken] | None = None) -> None:
        self._tokens: list[RefreshToken] = tokens or []
        self.created: list[RefreshToken] = []

    async def create(
        self,
        *,
        user_id: object,
        token_hash: str,
        expires_at: datetime,
    ) -> RefreshToken:
        now = datetime.now(UTC)
        rt = RefreshToken(
            id=uuid4(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked_at=None,
            created_at=now,
        )
        self._tokens.append(rt)
        self.created.append(rt)
        return rt

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        return next((t for t in self._tokens if t.token_hash == token_hash), None)

    async def revoke(self, token_id: object) -> None:
        for t in self._tokens:
            if t.id == token_id:
                t.revoked_at = datetime.now(UTC)
                break


def _make_service(
    user_repo: AbstractUserRepository | None = None,
    rt_repo: AbstractRefreshTokenRepository | None = None,
) -> AuthService:
    return AuthService(
        user_repo=user_repo or MockUserRepo(),
        refresh_token_repo=rt_repo or MockRefreshTokenRepo(),
    )


class TestRegister:
    async def test_register_success(self) -> None:
        svc = _make_service()
        user = await svc.register(email="new@example.com", username="alice", password="password123")
        assert user.email == "new@example.com"
        assert user.username == "alice"

    async def test_register_duplicate_email_raises_409(self) -> None:
        existing = _make_user(email="taken@example.com")
        svc = _make_service(user_repo=MockUserRepo([existing]))
        with pytest.raises(AppError) as exc_info:
            await svc.register(email="taken@example.com", username="bob", password="password123")
        assert exc_info.value.status_code == 409
        assert exc_info.value.code == ErrorCode.EMAIL_ALREADY_EXISTS


class TestLogin:
    async def test_login_success(self) -> None:
        user = _make_user(email="login@example.com", password="mypassword")
        svc = _make_service(user_repo=MockUserRepo([user]))
        returned_user, access_token, refresh_token = await svc.login(
            email="login@example.com",
            password="mypassword",
        )
        assert returned_user.id == user.id
        assert access_token != ""
        assert refresh_token != ""

    async def test_login_wrong_password(self) -> None:
        user = _make_user(email="login@example.com", password="correctpass")
        svc = _make_service(user_repo=MockUserRepo([user]))
        with pytest.raises(AppError) as exc_info:
            await svc.login(email="login@example.com", password="wrongpass")
        assert exc_info.value.status_code == 401
        assert exc_info.value.code == ErrorCode.INVALID_CREDENTIALS

    async def test_login_nonexistent_user(self) -> None:
        svc = _make_service(user_repo=MockUserRepo([]))
        with pytest.raises(AppError) as exc_info:
            await svc.login(email="ghost@example.com", password="any")
        assert exc_info.value.code == ErrorCode.INVALID_CREDENTIALS

    async def test_login_inactive_account(self) -> None:
        user = _make_user(email="inactive@example.com", password="pass1234", is_active=False)
        svc = _make_service(user_repo=MockUserRepo([user]))
        with pytest.raises(AppError) as exc_info:
            await svc.login(email="inactive@example.com", password="pass1234")
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == ErrorCode.USER_INACTIVE


class TestRefresh:
    async def test_refresh_success(self) -> None:
        user = _make_user()
        rt_repo = MockRefreshTokenRepo()
        user_repo = MockUserRepo([user])
        svc = _make_service(user_repo=user_repo, rt_repo=rt_repo)

        _, _, refresh_token = await svc.login(email=user.email, password="password123")
        initial_count = len(rt_repo.created)

        _, new_access, new_refresh = await svc.refresh(refresh_token_str=refresh_token)
        assert new_access != ""
        assert new_refresh != refresh_token
        assert len(rt_repo.created) == initial_count + 1

    async def test_refresh_revoked_token_rejected(self) -> None:
        user = _make_user()
        rt_str = create_refresh_token(user.id)
        rt = _make_rt(user, token_str=rt_str, revoked=True)
        svc = _make_service(user_repo=MockUserRepo([user]), rt_repo=MockRefreshTokenRepo([rt]))
        with pytest.raises(AppError) as exc_info:
            await svc.refresh(refresh_token_str=rt_str)
        assert exc_info.value.code == ErrorCode.REFRESH_TOKEN_REVOKED

    async def test_refresh_invalid_jwt_rejected(self) -> None:
        svc = _make_service()
        with pytest.raises(AppError) as exc_info:
            await svc.refresh(refresh_token_str="not.a.jwt")
        assert exc_info.value.status_code == 401


class TestLogout:
    async def test_logout_revokes_token(self) -> None:
        user = _make_user()
        rt_repo = MockRefreshTokenRepo()
        svc = _make_service(user_repo=MockUserRepo([user]), rt_repo=rt_repo)

        _, _, rt_str = await svc.login(email=user.email, password="password123")
        await svc.logout(refresh_token_str=rt_str)

        rt = await rt_repo.get_by_hash(hash_token(rt_str))
        assert rt is not None
        assert rt.revoked_at is not None

    async def test_logout_unknown_token_is_noop(self) -> None:
        user = _make_user()
        rt_str = create_refresh_token(user.id)
        svc = _make_service(user_repo=MockUserRepo([user]))
        await svc.logout(refresh_token_str=rt_str)  # should not raise


class TestGetCurrentUser:
    async def test_returns_user(self) -> None:
        user = _make_user()
        svc = _make_service(user_repo=MockUserRepo([user]))
        result = await svc.get_current_user(user.id)
        assert result.id == user.id

    async def test_raises_if_not_found(self) -> None:
        svc = _make_service(user_repo=MockUserRepo([]))
        with pytest.raises(UnauthorizedError):
            await svc.get_current_user(uuid4())
