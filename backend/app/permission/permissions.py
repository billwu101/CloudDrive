from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    VIEWER = "viewer"
    DOWNLOADER = "downloader"
    EDITOR = "editor"
    OWNER = "owner"


class LinkPermission(StrEnum):
    """What a *public* link may grant (design §6.12.4).

    Narrower than `Permission`: a link never grants `owner`. `EDITOR` is
    deliberately included (proposal §33) — handing write access to whoever holds
    the URL is the point of that feature — but it is bounded by the shared
    subtree and requires an expiry. The database enforces the same three values;
    without this type an out-of-range value travelled all the way to the insert
    and failed there as a 500.
    """

    VIEWER = "viewer"
    DOWNLOADER = "downloader"
    EDITOR = "editor"


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
