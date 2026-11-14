"""Application exceptions rendered as ``{"detail": ..., "code": ...}`` responses.

Raise these from services/routers; ``app.main`` registers a handler for ``AppError``.

Examples::

    raise NotFoundError("Turf not found")
    raise ConflictError("Slot is no longer available", code="SLOT_UNAVAILABLE")
    raise AppError(422, "Something odd", code="CUSTOM")
"""


class AppError(Exception):
    """Base application error mapped to an HTTP response by the global handler.

    Args:
        status_code: HTTP status code to return.
        detail: Human-readable message.
        code: Machine-readable error code (e.g. ``SLOT_UNAVAILABLE``); optional.
    """

    def __init__(self, status_code: int, detail: str, code: str | None = None) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code


class _HTTPStatusError(AppError):
    """Helper base for errors with a fixed status code and default code."""

    STATUS_CODE: int = 500
    DEFAULT_CODE: str = "INTERNAL_ERROR"
    DEFAULT_DETAIL: str = "Internal server error"

    def __init__(self, detail: str | None = None, code: str | None = None) -> None:
        super().__init__(
            self.STATUS_CODE,
            detail or self.DEFAULT_DETAIL,
            code or self.DEFAULT_CODE,
        )


class BadRequestError(_HTTPStatusError):
    """400 Bad Request."""

    STATUS_CODE = 400
    DEFAULT_CODE = "BAD_REQUEST"
    DEFAULT_DETAIL = "Bad request"


class UnauthorizedError(_HTTPStatusError):
    """401 Unauthorized."""

    STATUS_CODE = 401
    DEFAULT_CODE = "UNAUTHORIZED"
    DEFAULT_DETAIL = "Not authenticated"


class ForbiddenError(_HTTPStatusError):
    """403 Forbidden."""

    STATUS_CODE = 403
    DEFAULT_CODE = "FORBIDDEN"
    DEFAULT_DETAIL = "Not allowed"


class NotFoundError(_HTTPStatusError):
    """404 Not Found."""

    STATUS_CODE = 404
    DEFAULT_CODE = "NOT_FOUND"
    DEFAULT_DETAIL = "Not found"


class ConflictError(_HTTPStatusError):
    """409 Conflict."""

    STATUS_CODE = 409
    DEFAULT_CODE = "CONFLICT"
    DEFAULT_DETAIL = "Conflict"
