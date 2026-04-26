"""podpislon-sdk — unofficial async Python SDK for the Podpislon API.

This SDK is **not affiliated** with, endorsed by, or in any way officially
connected with the company that operates https://podpislon.ru.

Quick start
-----------
.. code-block:: python

    import asyncio
    from podpislon import PodpislonClient

    async def main():
        async with PodpislonClient(api_key="...") as client:
            info = await client.company.get_info()
            print("Signings left:", info.signings_left)

    asyncio.run(main())
"""

from __future__ import annotations

from podpislon.client import PodpislonClient
from podpislon.enums import DocumentStatus, WebhookEventType
from podpislon.exceptions import (
    PodpislonAPIError,
    PodpislonAuthenticationError,
    PodpislonConfigurationError,
    PodpislonError,
    PodpislonNotFoundError,
    PodpislonPermissionError,
    PodpislonRateLimitError,
    PodpislonServerError,
    PodpislonTransportError,
    PodpislonUnknownEventError,
    PodpislonValidationError,
    PodpislonWebhookError,
    PodpislonWebhookSignatureError,
)
from podpislon.models import (
    AddDocumentResult,
    APIResponse,
    ClientDataRequestSubmittedEvent,
    Company,
    CompanyInfo,
    Contact,
    Document,
    DocumentOpenedEvent,
    DocumentSignedEvent,
    Filter,
    PaginatedDocuments,
    PaginationMeta,
    Payment,
    PaymentSystem,
    WebhookEvent,
)
from podpislon.webhooks import WebhookHandler, WebhookSignatureVerifier, parse_event

try:
    from podpislon._version import __version__  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - source checkout without build step
    __version__ = "0.0.0+unknown"

__all__ = [
    # Client
    "PodpislonClient",
    # Enums
    "DocumentStatus",
    "WebhookEventType",
    # Models
    "APIResponse",
    "AddDocumentResult",
    "ClientDataRequestSubmittedEvent",
    "Company",
    "CompanyInfo",
    "Contact",
    "Document",
    "DocumentOpenedEvent",
    "DocumentSignedEvent",
    "Filter",
    "PaginatedDocuments",
    "PaginationMeta",
    "Payment",
    "PaymentSystem",
    "WebhookEvent",
    # Webhooks
    "WebhookHandler",
    "WebhookSignatureVerifier",
    "parse_event",
    # Exceptions
    "PodpislonAPIError",
    "PodpislonAuthenticationError",
    "PodpislonConfigurationError",
    "PodpislonError",
    "PodpislonNotFoundError",
    "PodpislonPermissionError",
    "PodpislonRateLimitError",
    "PodpislonServerError",
    "PodpislonTransportError",
    "PodpislonUnknownEventError",
    "PodpislonValidationError",
    "PodpislonWebhookError",
    "PodpislonWebhookSignatureError",
    # Version
    "__version__",
]
