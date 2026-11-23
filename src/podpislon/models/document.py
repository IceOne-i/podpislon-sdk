"""Document, filter, and add-document response models."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from podpislon.enums import DocumentStatus
from podpislon.models.common import PaginationMeta, _PodpislonBase
from podpislon.models.contact import Contact


class Filter(_PodpislonBase):
    """Search filter for ``POST /`` (list documents)."""

    fio: str | None = Field(default=None, description="Full-text search by name (ФИО).")
    dates: dict[str, str] | None = Field(
        default=None,
        description=(
            'Unix-timestamp range. Allowed keys: ">", ">=", "<", "<=" '
            "— combine to express open or closed intervals."
        ),
    )
    status: DocumentStatus | None = Field(default=None, description="Document status filter.")
    phone: str | None = Field(default=None, description="Phone number, digits-only is fine.")


class Document(_PodpislonBase):
    """A single document returned from ``POST /``."""

    id: int
    name: str | None = None
    status: DocumentStatus | None = None
    status_text: str | None = Field(
        default=None,
        description='Localised status string (e.g. "Подписан").',
    )
    sms: str | None = Field(default=None, description="One-time SMS code, when applicable.")
    date_create: datetime | None = Field(
        default=None,
        description="Document creation timestamp (UTC).",
    )
    contact: Contact | None = Field(
        default=None,
        description='Deprecated: prefer "contacts".',
    )
    contacts: list[Contact] = Field(default_factory=list)
    package: str | None = Field(
        default=None,
        description="Package identifier; needed by /resend/{package_id}.",
    )

    @field_validator("status", mode="before")
    @classmethod
    def _coerce_status(cls, v: Any) -> Any:
        # The API encodes status as a string; pydantic handles enum coercion
        # automatically, but ints occasionally appear in the wild.
        if isinstance(v, int):
            return str(v)
        return v


class PaginatedDocuments(_PodpislonBase):
    """Paginated wrapper produced by :meth:`DocumentsResource.list`."""

    items: list[Document] = Field(default_factory=list)
    pagination: PaginationMeta = Field(default_factory=PaginationMeta)

    def __iter__(self) -> Iterator[Document]:  # type: ignore[override]
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def has_next(self) -> bool:
        return self.pagination.has_next


class AddDocumentResult(_PodpislonBase):
    """Polymorphic response of ``PUT /add-document``.

    The API returns one of three shapes depending on the request:

    * a single integer ID (single document, sent via SMS);
    * a list of IDs (multiple documents, sent via SMS);
    * an object with ``ids`` and ``links`` (when ``no_sms=Y`` was used).

    This model normalises all three into one comfortable structure: ``ids``
    is always a list, ``links`` is empty unless the no-SMS branch was used.
    """

    ids: list[int] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Any) -> AddDocumentResult:
        if isinstance(raw, int):
            return cls(ids=[raw])
        if isinstance(raw, list):
            return cls(ids=[int(item) for item in raw])
        if isinstance(raw, dict):
            ids = [int(item) for item in raw.get("ids", [])]
            links = [str(item) for item in raw.get("links", [])]
            return cls(ids=ids, links=links)
        raise TypeError(f"Unexpected add-document result shape: {type(raw).__name__}")

    @property
    def first_id(self) -> int | None:
        return self.ids[0] if self.ids else None

    @property
    def first_link(self) -> str | None:
        return self.links[0] if self.links else None
