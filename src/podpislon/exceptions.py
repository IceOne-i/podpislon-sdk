"""Exception hierarchy for the Podpislon SDK.

All errors raised by the SDK inherit from :class:`PodpislonError`, so callers
can catch every SDK-related issue with a single ``except`` clause if desired.
HTTP-level failures are mapped to subclasses based on the response status,
which matches the conventions used by ``requests``-style libraries and makes
the SDK easy to integrate with existing error-handling code.
"""

from __future__ import annotations

from typing import Any, Mapping


class PodpislonError(Exception):
    """Base class for every error raised by the Podpislon SDK."""


class PodpislonConfigurationError(PodpislonError):
    """Raised when the SDK is constructed with an invalid configuration.

    Examples: missing API key, invalid base URL, conflicting parameters.
    """


class PodpislonAPIError(PodpislonError):
    """Raised when the API responds with a non-success status code."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.request_id = request_id

    def __str__(self) -> str:
        base = super().__str__()
        if self.status_code is not None:
            return f"[HTTP {self.status_code}] {base}"
        return base


class PodpislonAuthenticationError(PodpislonAPIError):
    """Raised on HTTP 401 — invalid or missing API key."""


class PodpislonPermissionError(PodpislonAPIError):
    """Raised on HTTP 403 — the resource is not accessible to your company."""


class PodpislonNotFoundError(PodpislonAPIError):
    """Raised on HTTP 404 — the requested entity does not exist."""


class PodpislonRateLimitError(PodpislonAPIError):
    """Raised on HTTP 429 — the per-key rate limit (4 RPS) has been exceeded.

    The SDK automatically retries throttled requests according to the
    configured retry policy. This exception is raised only when retries are
    exhausted.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded (4 requests per second per API key)",
        *,
        retry_after: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class PodpislonServerError(PodpislonAPIError):
    """Raised on HTTP 5xx — the API encountered an internal error."""


class PodpislonValidationError(PodpislonError):
    """Raised when request parameters fail client-side validation.

    Indicates a programming error in the calling code: the request was never
    sent over the wire because the SDK could detect that it would fail.
    """


class PodpislonTransportError(PodpislonError):
    """Raised on low-level transport failures: timeout, DNS failure, etc."""


class PodpislonWebhookError(PodpislonError):
    """Base class for errors raised while handling incoming webhooks."""


class PodpislonWebhookSignatureError(PodpislonWebhookError):
    """Raised when a webhook signature does not match the expected value."""


class PodpislonUnknownEventError(PodpislonWebhookError):
    """Raised when an incoming webhook payload has an unrecognised EVENT field."""


def raise_for_status(
    *,
    status_code: int,
    response_body: Any,
    request_id: str | None = None,
    headers: Mapping[str, str] | None = None,
) -> None:
    """Translate an HTTP error response into the appropriate SDK exception.

    Called by the transport layer after every request. ``status_code`` < 400
    is treated as success and the function returns silently.
    """

    if status_code < 400:
        return

    body_repr = _short_repr(response_body)
    common_kwargs = {
        "status_code": status_code,
        "response_body": response_body,
        "request_id": request_id,
    }

    if status_code == 401:
        raise PodpislonAuthenticationError(
            f"Authentication failed: {body_repr}", **common_kwargs
        )
    if status_code == 403:
        raise PodpislonPermissionError(
            f"Permission denied: {body_repr}", **common_kwargs
        )
    if status_code == 404:
        raise PodpislonNotFoundError(f"Not found: {body_repr}", **common_kwargs)
    if status_code == 429:
        retry_after = _parse_retry_after(headers)
        raise PodpislonRateLimitError(retry_after=retry_after, **common_kwargs)
    if 500 <= status_code < 600:
        raise PodpislonServerError(
            f"Server error: {body_repr}", **common_kwargs
        )
    raise PodpislonAPIError(
        f"Unexpected HTTP {status_code}: {body_repr}", **common_kwargs
    )


def _short_repr(body: Any) -> str:
    text = repr(body)
    if len(text) > 250:
        return text[:247] + "..."
    return text


def _parse_retry_after(headers: Mapping[str, str] | None) -> float | None:
    if not headers:
        return None
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
