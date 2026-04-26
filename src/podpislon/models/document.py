"""Document, filter, and add-document response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from podpislon.enums import DocumentStatus
from podpislon.models.common import PaginationMeta, _PodpislonBase
from podpislon.models.contact import Contact


class Filter(_PodpislonBase):
    """Search filter for ``POST /`` (list documents)."""

    fio: Optional[str] = Field(default=None, description="Full-text search by name (ФИО).")
    dates: Optional[Dict[str, str]] = Field(
        default=None,
        description=(
            'Unix-timestamp range. Allowed keys: ">", ">=", "<", "<=" '
            '— combine to express open or closed intervals.'
        ),
    )
    status: Optional[DocumentStatus] = Field(default=None, description="Document status filter.")
    phone: Optional[str] = Field(default=None, description="Phone number, digits-only is fine.")


class Document(_PodpislonBase):
    """A single document returned from ``POST /``."""

    id: int
    name: Optional[str] = None
    status: Optional[DocumentStatus] = None
    status_text: Optional[str] = Field(
        default=None,
        description='Localised status string (e.g. "Подписан").',
    )
    sms: Optional[str] = Field(default=None, description="One-time SMS code, when applicable.")
    date_create: Optional[datetime] = Field(
        default=None,
        description="Document creation timestamp (UTC).",
    )
    contact: Optional[Contact] = Field(
        default=None,
        description='Deprecated: prefer "contacts".',
    )
    contacts: List[Contact] = Field(default_factory=list)
    package: Optional[str] = Field(
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

    items: List[Document] = Field(default_factory=list)
    pagination: PaginationMeta = Field(default_factory=PaginationMeta)

    def __iter__(self):  # type: ignore[override]
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

    ids: List[int] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)

    @classmethod
    def from_api(cls, raw: Any) -> "AddDocumentResult":
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
    def first_id(self) -> Optional[int]:
        return self.ids[0] if self.ids else None

    @property
    def first_link(self) -> Optional[str]:
        return self.links[0] if self.links else None
