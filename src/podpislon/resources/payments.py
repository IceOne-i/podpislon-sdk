"""Payments resource — list of payment systems available to the company."""

from __future__ import annotations

from typing import List

from podpislon.models.payment import PaymentSystem
from podpislon.resources._base import Resource


class PaymentsResource(Resource):
    """Wraps ``GET /pay-systems``."""

    async def list_systems(self) -> List[PaymentSystem]:
        """Return every payment system enabled for the company."""

        response = await self._transport.request("GET", "/pay-systems")
        result = self._unwrap_status_envelope(response.json_body, expected_key="result")
        return [PaymentSystem.model_validate(item) for item in (result or [])]
