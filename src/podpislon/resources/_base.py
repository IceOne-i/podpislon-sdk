"""Common base class for resource modules."""

from __future__ import annotations

from typing import Any

from podpislon._transport import Transport
from podpislon.exceptions import PodpislonAPIError


class Resource:
    """Holds a reference to the shared transport.

    Resources are intentionally tiny: they translate Pythonic call-sites into
    HTTP requests and parse the response into pydantic models. Cross-cutting
    concerns (rate limiting, retries, error mapping) live in ``Transport``.
    """

    __slots__ = ("_transport",)

    def __init__(self, transport: Transport) -> None:
        self._transport = transport

    @staticmethod
    def _unwrap_status_envelope(body: Any, expected_key: str = "result") -> Any:
        """Validate the standard ``{status, result}`` envelope.

        The Podpislon API wraps successful responses in an envelope with a
        boolean ``status`` flag and a payload-specific key (usually
        ``result``, sometimes ``ok`` / ``mess`` for write operations). When
        ``status`` is ``False`` the API still returns HTTP 200, so we have to
        check it manually.
        """

        if not isinstance(body, dict):
            return body

        status = body.get("status")
        ok = body.get("ok")
        if status is False or ok is False:
            message = body.get("mess") or body.get("message") or "Unknown API error"
            raise PodpislonAPIError(
                f"API reported failure: {message}",
                response_body=body,
            )

        if expected_key in body:
            return body[expected_key]
        return body
