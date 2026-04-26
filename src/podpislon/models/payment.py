"""Payment-related models."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field, field_validator

from podpislon.models.common import _PodpislonBase


class Payment(_PodpislonBase):
    """A payment to be collected from the signer alongside the document."""

    pid: str = Field(..., description="ID of the payment system (see /pay-systems).")
    sum: str = Field(..., description="Amount as a string (the API stores it as text).")

    @field_validator("pid", "sum", mode="before")
    @classmethod
    def _coerce_to_str(cls, v: object) -> object:
        if isinstance(v, (int, float, Decimal)):
            return str(v)
        return v


class PaymentSystem(_PodpislonBase):
    """An entry from ``GET /pay-systems``."""

    id: int = Field(..., description="Internal payment system ID.")
    name: str = Field(..., description="Human-readable name (e.g. Robokassa).")
