"""Company-related response models."""

from __future__ import annotations

from pydantic import Field

from podpislon.models.common import _PodpislonBase


class Company(_PodpislonBase):
    """The legal entity that owns the API key."""

    name: str | None = Field(default=None, description='Company name (e.g. ООО "Рога и копыта").')
    inn: str | None = Field(default=None, description="Russian INN (taxpayer ID).")
    kpp: str | None = Field(default=None, description="Russian KPP (tax registration code).")


class CompanyInfo(_PodpislonBase):
    """Wrapper returned by ``GET /get-info``."""

    signings: str | None = Field(
        default=None,
        description="Remaining document signings on the current plan (string-encoded by the API).",
    )
    company: Company = Field(default_factory=Company)

    @property
    def signings_left(self) -> int | None:
        """Convenience: parse :attr:`signings` into an integer if possible."""

        if self.signings is None:
            return None
        try:
            return int(self.signings)
        except ValueError:
            return None
