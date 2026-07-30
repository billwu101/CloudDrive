from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    VIEWER = "viewer"
    DOWNLOADER = "downloader"
    EDITOR = "editor"
    OWNER = "owner"


class LinkPermission(StrEnum):
    """What a *public* link may grant (design §6.12.4).

    Deliberately narrower than `Permission`: a public link is opened by someone
    with no account, so "editor" would mean handing write access to anyone the
    URL reaches. The database enforces the same pair — and without this type the
    API accepted `editor`, letting the value travel all the way to the insert
    and fail there as a 500.
    """

    VIEWER = "viewer"
    DOWNLOADER = "downloader"


_LEVELS: dict[Permission, int] = {
    Permission.VIEWER: 1,
    Permission.DOWNLOADER: 2,
    Permission.EDITOR: 3,
    Permission.OWNER: 4,
}


def has_at_least(perm: Permission | None, required: Permission) -> bool:
    if perm is None:
        return False
    return _LEVELS[perm] >= _LEVELS[required]
