"""Generic helper models shared across resources."""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class _PodpislonBase(BaseModel):
    """Project-wide base class.

    * ``populate_by_name`` lets us declare ``snake_case`` field names while
      still accepting the upper-case keys (``EVENT``, ``COMPANY_ID``, …) that
      Podpislon uses for webhooks.
    * ``extra="ignore"`` keeps the SDK forward-compatible: extra response
      keys are silently ignored instead of raising validation errors.
    """

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
        validate_assignment=True,
        # The Podpislon API isn't always strict about types — for example,
        # `signings` and INN/KPP have been seen returning plain ints. Letting
        # pydantic coerce numeric scalars into str-typed fields keeps the SDK
        # forward-compatible without surprising the caller.
        coerce_numbers_to_str=True,
    )


class APIResponse(_PodpislonBase, Generic[T]):
    """Wrapper around the ``{status, result}`` envelope returned by the API."""

    status: bool = True
    result: T | None = None
    raw: dict[str, Any] | None = Field(
        default=None,
        description="Original JSON body, useful for debugging and forward-compat.",
    )


class PaginationMeta(_PodpislonBase):
    """Pagination metadata extracted from the ``x-pagination-*`` headers.

    Returned by :meth:`podpislon.resources.documents.DocumentsResource.list`
    so that callers can drive their own pagination loop without re-parsing
    response headers.
    """

    current_page: int | None = None
    page_count: int | None = None
    per_page: int | None = None
    total_count: int | None = None

    @property
    def has_next(self) -> bool:
        if self.current_page is None or self.page_count is None:
            return False
        return self.current_page < self.page_count
