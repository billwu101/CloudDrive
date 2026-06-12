from enum import StrEnum


class ActivityAction(StrEnum):
    CREATE = "create"
    UPLOAD = "upload"
    DOWNLOAD = "download"
    PREVIEW = "preview"
    RENAME = "rename"
    MOVE = "move"
    STAR = "star"
    TRASH = "trash"
    RESTORE = "restore"
    PERMANENT_DELETE = "permanent_delete"
    SHARE = "share"
    UNSHARE = "unshare"
    VERSION_CREATE = "version_create"
    VERSION_DELETE = "version_delete"
