from enum import StrEnum


class ErrorCode(StrEnum):
    # Auth
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    UNAUTHORIZED = "UNAUTHORIZED"
    REFRESH_TOKEN_REVOKED = "REFRESH_TOKEN_REVOKED"
    USER_INACTIVE = "USER_INACTIVE"

    # Authorization
    FORBIDDEN = "FORBIDDEN"

    # Resources
    NOT_FOUND = "NOT_FOUND"

    # Storage / quota
    QUOTA_EXCEEDED = "QUOTA_EXCEEDED"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"

    # Validation
    VALIDATION_ERROR = "VALIDATION_ERROR"

    # Drive / Storage
    NAME_CONFLICT = "NAME_CONFLICT"
    INVALID_OPERATION = "INVALID_OPERATION"
    ITEM_CONTENT_NOT_FOUND = "ITEM_CONTENT_NOT_FOUND"

    # Public share links. Deliberately a single code for "no such token",
    # "wrong password", "disabled" and "expired" — telling them apart would let
    # a caller enumerate valid tokens (design §6.12.11).
    SHARE_LINK_INVALID = "SHARE_LINK_INVALID"
    # Only ever returned for a *valid* password-protected link that was opened
    # without a password — i.e. the first request of the normal flow
    # (proposal §28.4). A wrong password returns SHARE_LINK_INVALID instead.
    SHARE_LINK_PASSWORD_REQUIRED = "SHARE_LINK_PASSWORD_REQUIRED"

    # Assistant
    ASSISTANT_UNAVAILABLE = "ASSISTANT_UNAVAILABLE"

    # Generic
    INTERNAL_ERROR = "INTERNAL_ERROR"
