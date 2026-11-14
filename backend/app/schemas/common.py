"""Common schemas: pagination and error responses."""

from collections.abc import Sequence
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """Generic paginated response: ``{items, total, page, page_size}``."""

    items: list[T]
    total: int
    page: int
    page_size: int

    @classmethod
    def create(cls, items: Sequence[T], total: int, params: "PaginationParams") -> "Page[T]":
        """Build a page from a slice of items, a total count and the request's params."""
        return cls(items=list(items), total=total, page=params.page, page_size=params.page_size)


class ErrorResponse(BaseModel):
    """Error body returned for all handled errors."""

    model_config = ConfigDict(json_schema_extra={"example": {"detail": "Not found", "code": None}})

    detail: str
    code: str | None = None


class PaginationParams:
    """Pagination query-params dependency (``page`` >= 1, 1 <= ``page_size`` <= 100).

    Usage::

        async def list_x(pagination: PaginationParams = Depends()): ...
            query.offset(pagination.offset).limit(pagination.limit)
    """

    def __init__(
        self,
        page: int = Query(1, ge=1, description="1-based page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        """Row offset for SQL ``OFFSET``."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Row limit for SQL ``LIMIT``."""
        return self.page_size
