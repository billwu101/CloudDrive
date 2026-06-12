from app.core.error_codes import ErrorCode


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
        *,
        status_code: int = 400,
    ) -> None:
        self.code = code
        self.message = message
        self.details: dict[str, object] = details or {}
        self.status_code = status_code
        super().__init__(message)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(ErrorCode.UNAUTHORIZED, message, status_code=401)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(ErrorCode.FORBIDDEN, message, status_code=403)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(ErrorCode.NOT_FOUND, message, status_code=404)


class QuotaExceededError(AppError):
    def __init__(self, message: str = "Storage quota exceeded") -> None:
        super().__init__(ErrorCode.QUOTA_EXCEEDED, message, status_code=413)


class NameConflictError(AppError):
    def __init__(self, message: str = "Name already exists") -> None:
        super().__init__(ErrorCode.NAME_CONFLICT, message, status_code=409)


class InvalidOperationError(AppError):
    def __init__(self, message: str = "Invalid operation") -> None:
        super().__init__(ErrorCode.INVALID_OPERATION, message, status_code=422)
