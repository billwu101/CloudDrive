from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.share import Share
from app.models.share_link import ShareLink
from app.models.user import User
from app.permission.permissions import Permission
from app.share.repository import AbstractShareLinkRepository, AbstractShareManagementRepository
from app.share.service import ShareLinkService, ShareService, _hash_token
from app.users.service import UserService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.users.test_service import MockUserRepo

# ── In-memory repositories ───────────────────────────────────────────────────


class MemShareManagementRepo(AbstractShareManagementRepository):
    def __init__(self, shares: list[Share] | None = None) -> None:
        self._shares: list[Share] = shares or []

    async def create(
        self, *, item_id: UUID, owner_id: UUID, target_user_id: UUID, permission: str
    ) -> Share:
        now = datetime.now(UTC)
        share = Share(
            id=uuid4(),
            item_id=item_id,
            owner_id=owner_id,
            target_user_id=target_user_id,
            permission=permission,
            created_at=now,
            updated_at=now,
        )
        self._shares.append(share)
        return share

    async def get_by_item_and_user(self, item_id: UUID, user_id: UUID) -> Share | None:
        return next(
            (s for s in self._shares if s.item_id == item_id and s.target_user_id == user_id),
            None,
        )

    async def update_permission(self, share_id: UUID, permission: str) -> Share:
        share = next(s for s in self._shares if s.id == share_id)
        share.permission = permission
        return share

    async def delete(self, share_id: UUID) -> None:
        self._shares = [s for s in self._shares if s.id != share_id]

    async def delete_by_item(self, item_id: UUID) -> None:
        self._shares = [s for s in self._shares if s.item_id != item_id]

    async def list_shared_with_me(
        self, user_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[Share], int]:
        matched = [s for s in self._shares if s.target_user_id == user_id]
        return matched[offset : offset + limit], len(matched)


class MemShareLinkRepo(AbstractShareLinkRepository):
    def __init__(self) -> None:
        self._links: list[ShareLink] = []

    async def create(
        self,
        *,
        item_id: UUID,
        token_hash: str,
        permission: str,
        password_hash: str | None,
        expires_at: datetime | None,
        created_by: UUID,
    ) -> ShareLink:
        link = ShareLink(
            id=uuid4(),
            item_id=item_id,
            token_hash=token_hash,
            permission=permission,
            password_hash=password_hash,
            expires_at=expires_at,
            is_active=True,
            created_by=created_by,
            created_at=datetime.now(UTC),
        )
        self._links.append(link)
        return link

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None:
        return next((lnk for lnk in self._links if lnk.token_hash == token_hash), None)

    async def deactivate(self, link_id: UUID) -> None:
        for lnk in self._links:
            if lnk.id == link_id:
                lnk.is_active = False


def _make_user(user_id: UUID | None = None, email: str = "target@test.com") -> User:
    now = datetime.now(UTC)
    return User(
        id=user_id or uuid4(),
        email=email,
        username="target",
        password_hash="h",
        avatar_url=None,
        quota_bytes=1_000_000,
        used_bytes=0,
        is_active=True,
        is_admin=False,
        created_at=now,
        updated_at=now,
    )


def _make_share_svc(
    item_repo: MemDriveItemRepo,
    target_user: User,
    shares: list[Share] | None = None,
) -> ShareService:
    return ShareService(
        item_repo=item_repo,
        share_repo=MemShareManagementRepo(shares),
        user_svc=UserService(repo=MockUserRepo(target_user)),
    )


def _make_link_svc(item_repo: MemDriveItemRepo) -> tuple[ShareLinkService, MemShareLinkRepo]:
    link_repo = MemShareLinkRepo()
    svc = ShareLinkService(item_repo=item_repo, link_repo=link_repo)
    return svc, link_repo


# ── ShareService tests ───────────────────────────────────────────────────────


async def test_owner_can_share() -> None:
    owner_id = uuid4()
    target = _make_user()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc = _make_share_svc(item_repo, target)

    resp = await svc.share_item(owner_id, item.id, target.email, Permission.VIEWER)
    assert resp.permission == Permission.VIEWER
    assert resp.target_user_id == target.id


async def test_non_owner_cannot_share() -> None:
    owner_id = uuid4()
    other = uuid4()
    target = _make_user()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc = _make_share_svc(item_repo, target)

    with pytest.raises(ForbiddenError):
        await svc.share_item(other, item.id, target.email, Permission.VIEWER)


async def test_share_target_email_not_found_raises() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc = ShareService(
        item_repo=item_repo,
        share_repo=MemShareManagementRepo(),
        user_svc=UserService(repo=MockUserRepo(None)),  # get_by_email returns None
    )
    with pytest.raises(NotFoundError):
        await svc.share_item(owner_id, item.id, "ghost@test.com", Permission.VIEWER)


async def test_cannot_share_with_self() -> None:
    owner_id = uuid4()
    owner_user = _make_user(user_id=owner_id)
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc = _make_share_svc(item_repo, owner_user)

    with pytest.raises(AppError) as exc_info:
        await svc.share_item(owner_id, item.id, owner_user.email, Permission.VIEWER)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_duplicate_share_updates_permission() -> None:
    owner_id = uuid4()
    target = _make_user()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    share_repo = MemShareManagementRepo()
    svc = ShareService(
        item_repo=item_repo,
        share_repo=share_repo,
        user_svc=UserService(repo=MockUserRepo(target)),
    )

    await svc.share_item(owner_id, item.id, target.email, Permission.VIEWER)
    resp = await svc.share_item(owner_id, item.id, target.email, Permission.EDITOR)

    assert resp.permission == Permission.EDITOR
    assert len(share_repo._shares) == 1  # no duplicate created


async def test_remove_share() -> None:
    owner_id = uuid4()
    target = _make_user()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    share_repo = MemShareManagementRepo()
    svc = ShareService(
        item_repo=item_repo,
        share_repo=share_repo,
        user_svc=UserService(repo=MockUserRepo(target)),
    )
    await svc.share_item(owner_id, item.id, target.email, Permission.VIEWER)
    await svc.remove_share(owner_id, item.id, target.id)
    assert len(share_repo._shares) == 0


async def test_list_shared_with_me() -> None:
    user_id = uuid4()
    target = _make_user(user_id=user_id)
    owner = uuid4()
    item = _item(owner_id=owner)
    item_repo = MemDriveItemRepo([item])
    share_repo = MemShareManagementRepo()
    svc = ShareService(
        item_repo=item_repo,
        share_repo=share_repo,
        user_svc=UserService(repo=MockUserRepo(target)),
    )
    # Share two different items with user
    await share_repo.create(
        item_id=item.id,
        owner_id=owner,
        target_user_id=user_id,
        permission=Permission.VIEWER,
    )
    page = await svc.list_shared_with_me(user_id)
    assert page.total == 1


# ── ShareLinkService tests ────────────────────────────────────────────────────


async def test_token_not_stored_in_plaintext() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, link_repo = _make_link_svc(item_repo)

    resp = await svc.create_link(owner_id, item.id, Permission.VIEWER)
    token = resp.token
    assert token is not None
    # The stored hash must NOT equal the plaintext token
    stored = link_repo._links[0]
    assert stored.token_hash != token
    assert stored.token_hash == _hash_token(token)


async def test_validate_link_with_correct_password() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, _ = _make_link_svc(item_repo)

    resp = await svc.create_link(owner_id, item.id, Permission.VIEWER, password="secret")
    token = resp.token
    assert token is not None
    link = await svc.validate_access(token, password="secret")
    assert link.item_id == item.id


async def test_validate_link_wrong_password_raises() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, _ = _make_link_svc(item_repo)

    resp = await svc.create_link(owner_id, item.id, Permission.VIEWER, password="correct")
    token = resp.token
    assert token is not None
    with pytest.raises(ForbiddenError):
        await svc.validate_access(token, password="wrong")


async def test_validate_expired_link_raises() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, _ = _make_link_svc(item_repo)

    past = datetime.now(UTC) - timedelta(hours=1)
    resp = await svc.create_link(owner_id, item.id, Permission.VIEWER, expires_at=past)
    token = resp.token
    assert token is not None
    with pytest.raises(AppError) as exc_info:
        await svc.validate_access(token)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_validate_deactivated_link_raises() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, link_repo = _make_link_svc(item_repo)

    resp = await svc.create_link(owner_id, item.id, Permission.VIEWER)
    token = resp.token
    assert token is not None
    link = link_repo._links[0]
    await svc.deactivate_link(owner_id, link.id)
    with pytest.raises(AppError) as exc_info:
        await svc.validate_access(token)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION
