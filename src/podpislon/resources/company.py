"""Company resource — single endpoint for retrieving account info."""

from __future__ import annotations

from podpislon.models.company import Company, CompanyInfo
from podpislon.resources._base import Resource


class CompanyResource(Resource):
    """Wraps ``GET /get-info``."""

    async def get_info(self) -> CompanyInfo:
        """Return company details and the remaining signing balance.

        Equivalent to::

            curl -H "X-Api-Key: $KEY" https://podpislon.ru/integration/get-info
        """

        response = await self._transport.request("GET", "/get-info")
        body = response.json_body or {}

        # The "company" envelope is at the top level (alongside "status" and
        # "signings"), so we hand-build CompanyInfo instead of using the
        # generic envelope unwrapper.
        company = Company.model_validate(body.get("company") or {})
        return CompanyInfo(signings=body.get("signings"), company=company)
