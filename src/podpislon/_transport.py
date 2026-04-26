"""Low-level async HTTP transport used by the resource layer.

Splits the HTTP plumbing (rate limiting, retries, error mapping, JSON
parsing) away from the resource methods so that each resource stays
focused on the business contract.
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Mapping, Sequence

import httpx

from podpislon._utils import AsyncRateLimiter
from podpislon.exceptions import (
    PodpislonAPIError,
    PodpislonRateLimitError,
    PodpislonServerError,
    PodpislonTransportError,
    raise_for_status,
)

_LOGGER = logging.getLogger("podpislon")


class RetryPolicy:
    """Exponential-backoff retry policy for transient failures."""

    __slots__ = ("max_retries", "backoff_factor", "max_backoff", "retry_on_statuses")

    def __init__(
        self,
        *,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: float = 30.0,
        retry_on_statuses: Sequence[int] = (429, 500, 502, 503, 504),
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if backoff_factor < 0:
            raise ValueError("backoff_factor must be >= 0")
        if max_backoff < 0:
            raise ValueError("max_backoff must be >= 0")
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_on_statuses = tuple(retry_on_statuses)

    def compute_delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Wait at least ``retry_after`` seconds, otherwise back off exponentially.

        A small random jitter (±25%) prevents the well-known thundering-herd
        when many parallel coroutines all retry at the same moment.
        """

        if retry_after is not None and retry_after > 0:
            return min(retry_after, self.max_backoff)
        base = self.backoff_factor * (2**attempt)
        jitter = random.uniform(0.75, 1.25)
        return min(base * jitter, self.max_backoff)


class Transport:
    """Thin wrapper around :class:`httpx.AsyncClient`.

    Responsibilities:

    * inject the ``X-Api-Key`` header on every request;
    * apply the global rate limiter (4 RPS);
    * retry transient failures (``429`` and ``5xx``);
    * convert HTTP failures to typed exceptions;
    * decode the JSON response body.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        timeout: float | httpx.Timeout,
        retry_policy: RetryPolicy,
        rate_limiter: AsyncRateLimiter | None,
        user_agent: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._retry_policy = retry_policy
        self._rate_limiter = rate_limiter
        self._user_agent = user_agent
        self._owns_client = client is None
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout,
            headers=self._default_headers(),
            follow_redirects=True,
        )
        if not self._owns_client:
            # Make sure caller-supplied clients still send our headers.
            for key, value in self._default_headers().items():
                self._client.headers.setdefault(key, value)

    def _default_headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Accept": "application/json",
            "User-Agent": self._user_agent,
        }

    @property
    def base_url(self) -> str:
        return self._base_url

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        data: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | Sequence[tuple[str, Any]] | None = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> "Response":
        """Issue an HTTP request and return the parsed response."""

        url = path if path.startswith(("http://", "https://")) else path
        attempt = 0
        last_exc: Exception | None = None

        while True:
            try:
                if self._rate_limiter is not None:
                    async with self._rate_limiter.slot():
                        http_response = await self._client.request(
                            method,
                            url,
                            json=json,
                            data=data,
                            files=files,
                            params=params,
                            headers=headers,
                        )
                else:
                    http_response = await self._client.request(
                        method,
                        url,
                        json=json,
                        data=data,
                        files=files,
                        params=params,
                        headers=headers,
                    )
            except httpx.TimeoutException as exc:
                last_exc = exc
                _LOGGER.debug("Timeout on %s %s (attempt %d)", method, url, attempt)
                if attempt >= self._retry_policy.max_retries:
                    raise PodpislonTransportError(f"Request timed out: {exc}") from exc
                await asyncio.sleep(self._retry_policy.compute_delay(attempt))
                attempt += 1
                continue
            except httpx.TransportError as exc:
                last_exc = exc
                _LOGGER.debug(
                    "Transport error on %s %s (attempt %d): %s", method, url, attempt, exc
                )
                if attempt >= self._retry_policy.max_retries:
                    raise PodpislonTransportError(str(exc)) from exc
                await asyncio.sleep(self._retry_policy.compute_delay(attempt))
                attempt += 1
                continue

            status = http_response.status_code

            if (
                status in self._retry_policy.retry_on_statuses
                and attempt < self._retry_policy.max_retries
            ):
                retry_after = _parse_retry_after(http_response.headers)
                delay = self._retry_policy.compute_delay(attempt, retry_after)
                _LOGGER.debug(
                    "Retrying %s %s after %.2fs (status=%s, attempt=%d)",
                    method,
                    url,
                    delay,
                    status,
                    attempt,
                )
                await asyncio.sleep(delay)
                attempt += 1
                continue

            response = Response.from_httpx(http_response)

            try:
                raise_for_status(
                    status_code=status,
                    response_body=response.json_body if response.is_json else response.text,
                    request_id=response.request_id,
                    headers=http_response.headers,
                )
            except (PodpislonRateLimitError, PodpislonServerError):
                raise
            except PodpislonAPIError:
                raise

            return response

        # Unreachable, but mypy/typing wants an explicit raise.
        if last_exc is not None:  # pragma: no cover
            raise PodpislonTransportError(str(last_exc)) from last_exc
        raise PodpislonTransportError("Unknown transport error")  # pragma: no cover


class Response:
    """Lightweight wrapper that exposes JSON / headers / status without httpx leaking out."""

    __slots__ = ("status_code", "headers", "text", "_json_body", "_is_json", "request_id")

    def __init__(
        self,
        *,
        status_code: int,
        headers: Mapping[str, str],
        text: str,
        json_body: Any,
        is_json: bool,
        request_id: str | None,
    ) -> None:
        self.status_code = status_code
        self.headers = headers
        self.text = text
        self._json_body = json_body
        self._is_json = is_json
        self.request_id = request_id

    @property
    def json_body(self) -> Any:
        return self._json_body

    @property
    def is_json(self) -> bool:
        return self._is_json

    @classmethod
    def from_httpx(cls, response: httpx.Response) -> "Response":
        content_type = response.headers.get("content-type", "")
        is_json = "application/json" in content_type.lower()
        json_body: Any = None
        if is_json and response.content:
            try:
                json_body = response.json()
            except ValueError:
                is_json = False
        return cls(
            status_code=response.status_code,
            headers=dict(response.headers),
            text=response.text,
            json_body=json_body,
            is_json=is_json,
            request_id=response.headers.get("x-request-id"),
        )


def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("Retry-After") or headers.get("retry-after")
    if not raw:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None
