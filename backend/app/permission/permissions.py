from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    VIEWER = "viewer"
    DOWNLOADER = "downloader"
    EDITOR = "editor"
    OWNER = "owner"


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
