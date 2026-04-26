"""Contact model — a person who needs to sign a document."""

from __future__ import annotations

from pydantic import Field

from podpislon.models.common import _PodpislonBase


class Contact(_PodpislonBase):
    """A signer / addressee of a document."""

    name: str = Field(..., description="First name (имя)")
    second_name: str | None = Field(
        default=None,
        description="Patronymic (отчество)",
    )
    last_name: str = Field(..., description="Last name (фамилия)")
    phone: str = Field(
        ...,
        description=(
            "Phone in one of: +7 (XXX) XXX-XX-XX, 8 (XXX) XXX-XX-XX, "
            "8XXXXXXXXXX, +7XXXXXXXXXX"
        ),
    )
    sid: str | None = Field(
        default=None,
        description="Server-assigned signer ID (returned by the API).",
    )
    link: str | None = Field(
        default=None,
        description="Direct signing link (returned when no_sms=Y was used).",
    )
