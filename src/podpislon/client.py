"""High-level async client for the Podpislon API.

Typical usage::

    from podpislon import PodpislonClient

    async with PodpislonClient(api_key="...") as client:
        info = await client.company.get_info()
        async for doc in client.documents.iter_all():
            print(doc.id, doc.name)

The client is a thin façade: each remote resource lives on its own
attribute (``client.documents``, ``client.company``, ``client.payments``)
and shares a single underlying transport. This keeps the public surface
discoverable via tab-completion and matches the layout of every
well-loved Python SDK (``stripe.Customer``, ``boto3.client(...).list_*``).
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Type

import httpx

from podpislon._transport import RetryPolicy, Transport
from podpislon._utils import AsyncRateLimiter
from podpislon.exceptions import PodpislonConfigurationError
from podpislon.resources.company import CompanyResource
from podpislon.resources.documents import DocumentsResource
from podpislon.resources.payments import PaymentsResource

DEFAULT_BASE_URL = "https://podpislon.ru/integration"
DEFAULT_TIMEOUT = 30.0
DEFAULT_USER_AGENT = "podpislon-sdk-python (+https://github.com/IceOne-i/podpislon-sdk)"


class PodpislonClient:
    """Async API client for the Podpislon document-signing service.

    Parameters
    ----------
    api_key:
        The API key generated in the Podpislon dashboard
        (`Личный кабинет → Интеграции <https://podpislon.ru/lk/integrations>`_).
    base_url:
        Override the API root. Useful only for staging environments.
    timeout:
        Per-request timeout in seconds, or an :class:`httpx.Timeout` for
        fine-grained control.
    max_retries:
        Number of retries for transient failures (``429``, ``5xx``, network
        errors). Set to ``0`` to disable retries.
    rate_limit:
        Maximum requests per second to enforce client-side. The Podpislon API
        documents a 4 RPS limit per key; the SDK matches that by default.
        Set to ``None`` to disable the limiter (e.g. when running tests).
    user_agent:
        Custom ``User-Agent`` header. Defaults to the SDK identifier.
    http_client:
        Inject your own preconfigured :class:`httpx.AsyncClient` (proxy,
        custom transport, mTLS, etc.). When supplied, the SDK will NOT close
        it on exit — that's your responsibility.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx.Timeout = DEFAULT_TIMEOUT,
        max_retries: int = 3,
        rate_limit: int | None = 4,
        user_agent: str = DEFAULT_USER_AGENT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key or not isinstance(api_key, str):
            raise PodpislonConfigurationError(
                "api_key must be a non-empty string. Generate one in the "
                "Podpislon dashboard at https://podpislon.ru/lk/integrations."
            )
        if not base_url:
            raise PodpislonConfigurationError("base_url must be a non-empty string")

        self._closed = False
        self._transport = Transport(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            retry_policy=RetryPolicy(max_retries=max_retries),
            rate_limiter=AsyncRateLimiter(rate_limit) if rate_limit else None,
            user_agent=user_agent,
            client=http_client,
        )

        self.documents = DocumentsResource(self._transport)
        self.company = CompanyResource(self._transport)
        self.payments = PaymentsResource(self._transport)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    async def __aenter__(self) -> "PodpislonClient":
        return self

    async def __aexit__(
        self,
        exc_type: Type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool.

        Safe to call multiple times; subsequent calls are no-ops.
        """

        if self._closed:
            return
        self._closed = True
        await self._transport.aclose()

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    @property
    def base_url(self) -> str:
        return self._transport.base_url

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        return f"PodpislonClient(base_url={self.base_url!r})"

    # Allow `await client(...)` style ergonomic helpers in the future
    # without breaking back-compat.
    async def request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Escape hatch for endpoints not yet wrapped by the SDK.

        Returns the raw decoded JSON body. Use sparingly — prefer the typed
        resource methods.
        """

        response = await self._transport.request(method, path, **kwargs)
        return response.json_body if response.is_json else response.text
