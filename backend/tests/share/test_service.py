from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, ForbiddenError, NotFoundError
from app.models.drive_item import DriveItem
from app.models.share import Share
from app.models.share_link import ShareLink
from app.models.user import User
from app.permission.permissions import LinkPermission, Permission
from app.share.repository import (
    AbstractShareLinkRepository,
    AbstractShareManagementRepository,
    ShareBadges,
    SharedByMeRow,
)
from app.share.service import ShareLinkService, ShareService, _hash_token
from app.users.service import UserService
from tests.drive.test_service import MemDriveItemRepo, _item
from tests.users.test_service import MockUserRepo

# ── In-memory repositories ───────────────────────────────────────────────────


class MemShareManagementRepo(AbstractShareManagementRepository):
    def __init__(
        self,
        shares: list[Share] | None = None,
        *,
        items: list[DriveItem] | None = None,
        links: list[ShareLink] | None = None,
        users: dict[UUID, User] | None = None,
    ) -> None:
        self._shares: list[Share] = shares or []
        # Only the "shared by me" view needs to resolve items/links/users;
        # the older tests construct this repo with shares alone.
        self.items = items or []
        self.links = links or []
        self.users = users or {}

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

    async def list_shared_by_me(
        self, owner_id: UUID, *, offset: int, limit: int
    ) -> tuple[list[SharedByMeRow], int]:
        items = {i.id: i for i in (self.items or [])}
        by_item: dict[UUID, SharedByMeRow] = {}
        for share in self._shares:
            if share.owner_id != owner_id:
                continue
            item = items.get(share.item_id)
            if item is None or item.is_deleted:
                continue
            row = by_item.setdefault(item.id, SharedByMeRow(item=item, shares=[], links=[]))
            row.shares.append((share, self.users.get(share.target_user_id) or _make_user()))
        for link in self.links:
            if link.created_by != owner_id:
                continue
            item = items.get(link.item_id)
            if item is None or item.is_deleted:
                continue
            row = by_item.setdefault(item.id, SharedByMeRow(item=item, shares=[], links=[]))
            row.links.append(link)
        rows = list(by_item.values())
        return rows[offset : offset + limit], len(rows)

    async def get_share_badges(
        self, owner_id: UUID, item_ids: list[UUID]
    ) -> dict[UUID, ShareBadges]:
        now = datetime.now(UTC)
        shared = {s.item_id for s in self._shares if s.owner_id == owner_id}
        linked = {
            lnk.item_id
            for lnk in self.links
            if lnk.created_by == owner_id
            and lnk.is_active
            and (lnk.expires_at is None or lnk.expires_at > now)
        }
        return {
            item_id: ShareBadges(
                shared_with_users=item_id in shared,
                has_active_public_link=item_id in linked,
            )
            for item_id in item_ids
        }


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
        token_encrypted: str | None = None,
    ) -> ShareLink:
        link = ShareLink(
            id=uuid4(),
            item_id=item_id,
            token_hash=token_hash,
            token_encrypted=token_encrypted,
            permission=permission,
            password_hash=password_hash,
            expires_at=expires_at,
            is_active=True,
            created_by=created_by,
            created_at=datetime.now(UTC),
            # Column defaults are applied on flush, which never happens here —
            # set them explicitly so the fake matches a persisted row.
            attempt_window_start=None,
            attempt_count=0,
            locked_until=None,
        )
        self._links.append(link)
        return link

    async def get_by_token_hash(self, token_hash: str) -> ShareLink | None:
        return next((lnk for lnk in self._links if lnk.token_hash == token_hash), None)

    async def get_by_id(self, link_id: UUID) -> ShareLink | None:
        return next((lnk for lnk in self._links if lnk.id == link_id), None)

    async def update_attempt_state(
        self,
        link_id: UUID,
        *,
        window_start: datetime | None,
        count: int,
        locked_until: datetime | None,
    ) -> None:
        for lnk in self._links:
            if lnk.id == link_id:
                lnk.attempt_window_start = window_start
                lnk.attempt_count = count
                lnk.locked_until = locked_until

    async def deactivate(self, link_id: UUID) -> None:
        for lnk in self._links:
            if lnk.id == link_id:
                lnk.is_active = False

    async def delete(self, link_id: UUID) -> None:
        self._links = [lnk for lnk in self._links if lnk.id != link_id]


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

    resp = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)
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

    resp = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER, password="secret")
    token = resp.token
    assert token is not None
    link = await svc.validate_access(token, password="secret")
    assert link.item_id == item.id


async def test_validate_link_wrong_password_raises() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    item_repo = MemDriveItemRepo([item])
    svc, _ = _make_link_svc(item_repo)

    resp = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER, password="correct")
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
    resp = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER, expires_at=past)
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

    resp = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)
    token = resp.token
    assert token is not None
    link = link_repo._links[0]
    await svc.deactivate_link(owner_id, link.id)
    with pytest.raises(AppError) as exc_info:
        await svc.validate_access(token)
    assert exc_info.value.code == ErrorCode.INVALID_OPERATION


async def test_deactivate_link_rejects_a_stranger() -> None:
    """Regression: any signed-in user could disable any link they knew the id of."""
    owner_id, other_id = uuid4(), uuid4()
    item = _item(owner_id=owner_id)
    items = MemDriveItemRepo([item])
    svc, links = _make_link_svc(items)
    created = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)

    with pytest.raises(ForbiddenError):
        await svc.deactivate_link(other_id, created.id)

    stored = await links.get_by_id(created.id)
    assert stored is not None and stored.is_active is True

    await svc.deactivate_link(owner_id, created.id)
    stored = await links.get_by_id(created.id)
    assert stored is not None and stored.is_active is False


# ── Shared by me (proposal §29) ──────────────────────────────────────────────


def _shared_by_me_svc(
    owner_id: UUID,
    items: list[DriveItem],
    shares: list[Share],
    links: list[ShareLink],
    users: dict[UUID, User] | None = None,
) -> ShareService:
    item_repo = MemDriveItemRepo(items)
    return ShareService(
        item_repo=item_repo,
        share_repo=MemShareManagementRepo(shares, items=items, links=links, users=users),
        user_svc=UserService(repo=MockUserRepo(_make_user())),
    )


def _share_row(item_id: UUID, owner_id: UUID, target_id: UUID, permission: str) -> Share:
    now = datetime.now(UTC)
    return Share(
        id=uuid4(),
        item_id=item_id,
        owner_id=owner_id,
        target_user_id=target_id,
        permission=permission,
        created_at=now,
        updated_at=now,
    )


def _link_row(
    item_id: UUID,
    created_by: UUID,
    *,
    password_hash: str | None = None,
    expires_at: datetime | None = None,
    is_active: bool = True,
) -> ShareLink:
    return ShareLink(
        id=uuid4(),
        item_id=item_id,
        token_hash=uuid4().hex,
        permission="viewer",
        password_hash=password_hash,
        expires_at=expires_at,
        is_active=is_active,
        created_by=created_by,
        created_at=datetime.now(UTC),
        attempt_window_start=None,
        attempt_count=0,
        locked_until=None,
    )


async def test_shared_by_me_groups_every_share_of_an_item_into_one_entry() -> None:
    """§29.3 criterion 4 — three people plus a link is one row, not four."""
    owner = uuid4()
    item = _item(owner_id=owner, name="Deck")
    people = [_make_user(email=f"p{i}@test.com") for i in range(3)]
    shares = [_share_row(item.id, owner, p.id, "viewer") for p in people]
    links = [_link_row(item.id, owner)]
    svc = _shared_by_me_svc(owner, [item], shares, links, {p.id: p for p in people})

    page = await svc.list_shared_by_me(owner)

    assert page.total == 1
    entry = page.items[0]
    assert entry.item.name == "Deck"
    assert len(entry.user_shares) == 3
    assert len(entry.links) == 1
    assert {u.email for u in entry.user_shares} == {"p0@test.com", "p1@test.com", "p2@test.com"}


async def test_shared_by_me_reports_password_as_a_flag_not_a_hash() -> None:
    owner = uuid4()
    item = _item(owner_id=owner)
    links = [_link_row(item.id, owner, password_hash="$argon2id$super-secret")]
    svc = _shared_by_me_svc(owner, [item], [], links)

    entry = (await svc.list_shared_by_me(owner)).items[0]

    assert entry.links[0].has_password is True
    assert "argon2" not in entry.links[0].model_dump_json()


async def test_shared_by_me_keeps_dead_links_but_marks_them_inactive() -> None:
    """An expired link still tells the owner it once existed (§29.2 rule 2)."""
    owner = uuid4()
    item = _item(owner_id=owner)
    links = [
        _link_row(item.id, owner, is_active=False),
        _link_row(item.id, owner, expires_at=datetime.now(UTC) - timedelta(hours=1)),
    ]
    svc = _shared_by_me_svc(owner, [item], [], links)

    entry = (await svc.list_shared_by_me(owner)).items[0]

    assert len(entry.links) == 2
    assert all(lnk.is_active is False for lnk in entry.links)
    assert entry.item.has_active_public_link is False


async def test_shared_by_me_excludes_trashed_items() -> None:
    owner = uuid4()
    live = _item(owner_id=owner, name="Live")
    trashed = _item(owner_id=owner, name="Trashed", is_deleted=True)
    shares = [
        _share_row(live.id, owner, uuid4(), "viewer"),
        _share_row(trashed.id, owner, uuid4(), "viewer"),
    ]
    svc = _shared_by_me_svc(owner, [live, trashed], shares, [])

    page = await svc.list_shared_by_me(owner)

    assert [e.item.name for e in page.items] == ["Live"]


async def test_shared_by_me_ignores_other_owners_shares() -> None:
    owner, stranger = uuid4(), uuid4()
    mine = _item(owner_id=owner, name="Mine")
    theirs = _item(owner_id=stranger, name="Theirs")
    shares = [
        _share_row(mine.id, owner, uuid4(), "viewer"),
        _share_row(theirs.id, stranger, uuid4(), "viewer"),
    ]
    svc = _shared_by_me_svc(owner, [mine, theirs], shares, [])

    page = await svc.list_shared_by_me(owner)

    assert [e.item.name for e in page.items] == ["Mine"]


async def test_shared_by_me_is_empty_when_nothing_is_shared() -> None:
    owner = uuid4()
    item = _item(owner_id=owner)
    svc = _shared_by_me_svc(owner, [item], [], [])

    page = await svc.list_shared_by_me(owner)

    assert page.total == 0
    assert page.items == []


# ── deleting a dead link's record (proposal §29.2 rule 4.1) ──────────────────


async def test_a_disabled_link_record_can_be_deleted() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    items = MemDriveItemRepo([item])
    svc, links = _make_link_svc(items)
    created = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)
    await svc.deactivate_link(owner_id, created.id)

    await svc.delete_link_record(owner_id, created.id)

    assert await links.get_by_id(created.id) is None


async def test_an_expired_link_record_can_be_deleted() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    items = MemDriveItemRepo([item])
    svc, links = _make_link_svc(items)
    created = await svc.create_link(
        owner_id,
        item.id,
        LinkPermission.VIEWER,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )

    await svc.delete_link_record(owner_id, created.id)

    assert await links.get_by_id(created.id) is None


async def test_removing_a_live_link_revokes_it_outright() -> None:
    """One action, no disable step first (proposal §29.5 decision 4, revised).

    Deleting the row *is* the revocation: guest access resolves through it, so
    the link stops working the moment it is gone. There is no undo.
    """
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    items = MemDriveItemRepo([item])
    svc, links = _make_link_svc(items)
    created = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)

    await svc.delete_link_record(owner_id, created.id)

    assert await links.get_by_id(created.id) is None


async def test_a_stranger_cannot_delete_a_link_record() -> None:
    owner_id, other_id = uuid4(), uuid4()
    item = _item(owner_id=owner_id)
    items = MemDriveItemRepo([item])
    svc, links = _make_link_svc(items)
    created = await svc.create_link(owner_id, item.id, LinkPermission.VIEWER)
    await svc.deactivate_link(owner_id, created.id)

    with pytest.raises(ForbiddenError):
        await svc.delete_link_record(other_id, created.id)

    assert await links.get_by_id(created.id) is not None


# ── link URL recovery + editor password (proposal §29.2 rule 7, §33.3 rule 4) ──


async def test_the_owner_can_get_the_original_url_back() -> None:
    """proposal §29.3 criterion 3.2 — the same token that was handed out."""
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    svc, _ = _make_link_svc(MemDriveItemRepo([item]))

    created = await svc.create_link(owner_id, item.id, LinkPermission.DOWNLOADER)
    revealed = await svc.reveal_token(owner_id, created.id)

    assert revealed == created.token


async def test_only_the_owner_can_get_the_url_back() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    svc, _ = _make_link_svc(MemDriveItemRepo([item]))
    created = await svc.create_link(owner_id, item.id, LinkPermission.DOWNLOADER)

    with pytest.raises(ForbiddenError):
        await svc.reveal_token(uuid4(), created.id)


async def test_a_link_from_before_the_column_cannot_be_recovered() -> None:
    """Saying so is the honest answer — there is nothing stored to return."""
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    svc, link_repo = _make_link_svc(MemDriveItemRepo([item]))
    created = await svc.create_link(owner_id, item.id, LinkPermission.DOWNLOADER)
    stored = await link_repo.get_by_id(created.id)
    assert stored is not None
    stored.token_encrypted = None

    with pytest.raises(NotFoundError):
        await svc.reveal_token(owner_id, created.id)


async def test_an_editor_link_needs_a_password_as_well_as_an_expiry() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    svc, _ = _make_link_svc(MemDriveItemRepo([item]))
    later = datetime.now(UTC) + timedelta(days=1)

    with pytest.raises(AppError) as no_password:
        await svc.create_link(owner_id, item.id, LinkPermission.EDITOR, expires_at=later)
    assert no_password.value.status_code == 422

    with pytest.raises(AppError) as no_expiry:
        await svc.create_link(owner_id, item.id, LinkPermission.EDITOR, password="s3cret")
    assert no_expiry.value.status_code == 422

    ok = await svc.create_link(
        owner_id, item.id, LinkPermission.EDITOR, password="s3cret", expires_at=later
    )
    assert ok.permission == LinkPermission.EDITOR.value


async def test_the_password_rule_does_not_touch_the_lower_tiers() -> None:
    owner_id = uuid4()
    item = _item(owner_id=owner_id)
    svc, _ = _make_link_svc(MemDriveItemRepo([item]))

    for tier in (LinkPermission.VIEWER, LinkPermission.DOWNLOADER):
        created = await svc.create_link(owner_id, item.id, tier)
        assert created.token is not None
