"""Company-related response models."""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from podpislon.models.common import _PodpislonBase


class Company(_PodpislonBase):
    """The legal entity that owns the API key."""

    name: str | None = Field(default=None, description='Company name (e.g. ООО "Рога и копыта").')
    inn: str | None = Field(default=None, description="Russian INN (taxpayer ID).")
    kpp: str | None = Field(default=None, description="Russian KPP (tax registration code).")

    @field_validator("name", "inn", "kpp", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: Any) -> Any:
        # The API has been observed returning numeric INN/KPP as plain ints;
        # cast scalars to strings so validation doesn't reject them.
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, (int, float)):
            return str(v)
        return v


class CompanyInfo(_PodpislonBase):
    """Wrapper returned by ``GET /get-info``."""

    signings: str | None = Field(
        default=None,
        description=(
            "Remaining document signings on the current plan. The API has "
            "been seen returning either a string or an integer; both shapes "
            "are accepted and exposed as a string here."
        ),
    )
    company: Company = Field(default_factory=Company)

    @field_validator("signings", mode="before")
    @classmethod
    def _coerce_signings(cls, v: Any) -> Any:
        if v is None or isinstance(v, str):
            return v
        if isinstance(v, bool):
            # Avoid the bool-is-an-int trap: don't let True/False sneak in.
            return str(int(v))
        if isinstance(v, (int, float)):
            return str(v)
        return v

    @property
    def signings_left(self) -> int | None:
        """Convenience: parse :attr:`signings` into an integer if possible."""

        if self.signings is None:
            return None
        try:
            return int(self.signings)
        except ValueError:
            return None
