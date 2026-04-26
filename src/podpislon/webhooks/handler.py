"""High-level webhook dispatch.

The handler stays framework-agnostic on purpose: ``dispatch`` accepts any
payload that :func:`podpislon.webhooks.parser.parse_event` can understand,
so wiring it into FastAPI / aiohttp / aiogram / Sanic is a one-liner.
"""

from __future__ import annotations

import asyncio
import hmac
import inspect
import logging
from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, List, Optional, Type, Union

from podpislon.enums import WebhookEventType
from podpislon.exceptions import PodpislonWebhookSignatureError
from podpislon.models.webhook import (
    ClientDataRequestSubmittedEvent,
    DocumentOpenedEvent,
    DocumentSignedEvent,
)
from podpislon.webhooks.parser import WebhookPayload, parse_event

EventModel = Union[
    DocumentOpenedEvent,
    DocumentSignedEvent,
    ClientDataRequestSubmittedEvent,
]
EventHandler = Callable[[EventModel], Union[None, Awaitable[None]]]

_LOGGER = logging.getLogger("podpislon.webhooks")


class WebhookSignatureVerifier:
    """Verify the ``SIGNATURE`` field on incoming events.

    Podpislon's public documentation does not publish the exact signing
    algorithm, but commonly used schemes are HMAC-SHA256 (or SHA1) over the
    serialised payload with the company's secret key. The verifier accepts a
    ``compute`` callable so you can plug in whatever scheme your account
    uses without subclassing.

    .. note::
       Skip signature verification if you've not been told the algorithm.
       Use IP allow-listing or a shared secret in the URL as a fallback.
    """

    def __init__(
        self,
        secret: str,
        *,
        compute: Optional[Callable[[bytes, str], str]] = None,
    ) -> None:
        if not secret:
            raise ValueError("secret must be a non-empty string")
        self._secret = secret
        self._compute = compute or self._default_hmac_sha256

    def verify(self, *, raw_body: bytes, signature: str) -> bool:
        expected = self._compute(raw_body, self._secret)
        return hmac.compare_digest(expected, signature)

    def assert_valid(self, *, raw_body: bytes, signature: str) -> None:
        if not self.verify(raw_body=raw_body, signature=signature):
            raise PodpislonWebhookSignatureError(
                "Webhook signature does not match the expected value"
            )

    @staticmethod
    def _default_hmac_sha256(raw_body: bytes, secret: str) -> str:
        import hashlib

        return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


class WebhookHandler:
    """Register typed handlers and dispatch incoming events to them.

    Handlers can be sync or async. ``dispatch`` always returns the list of
    results so you can collect responses (e.g. for fan-out logic).

    Usage::

        handler = WebhookHandler()

        @handler.on(WebhookEventType.DOCUMENT_SIGNED)
        async def signed(event: DocumentSignedEvent) -> None:
            await db.mark_signed(event.file_id)

        @handler.on_any
        async def audit(event):
            await audit_log.write(event)
    """

    def __init__(
        self,
        *,
        signature_verifier: Optional[WebhookSignatureVerifier] = None,
    ) -> None:
        self._handlers: DefaultDict[WebhookEventType, List[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: List[EventHandler] = []
        self._signature_verifier = signature_verifier

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def on(
        self,
        event_type: WebhookEventType,
    ) -> Callable[[EventHandler], EventHandler]:
        """Register a handler for a specific event type."""

        if not isinstance(event_type, WebhookEventType):
            raise TypeError("event_type must be a WebhookEventType member")

        def decorator(func: EventHandler) -> EventHandler:
            self._handlers[event_type].append(func)
            return func

        return decorator

    def on_any(self, func: EventHandler) -> EventHandler:
        """Register a handler that fires for every event."""

        self._wildcard_handlers.append(func)
        return func

    def add_listener(
        self,
        event_type: WebhookEventType,
        handler: EventHandler,
    ) -> None:
        """Imperative alternative to :meth:`on` for non-decorator code paths."""

        self._handlers[event_type].append(handler)

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    async def dispatch(
        self,
        payload: WebhookPayload,
        *,
        raw_body: Optional[bytes] = None,
    ) -> EventModel:
        """Parse, verify and dispatch a payload. Returns the parsed event."""

        if self._signature_verifier is not None:
            if raw_body is None:
                if isinstance(payload, (bytes, bytearray)):
                    raw_body = bytes(payload)
                else:
                    raise PodpislonWebhookSignatureError(
                        "Signature verification requires the raw request body. "
                        "Pass raw_body= explicitly when payload is not bytes."
                    )
            event = parse_event(payload)
            self._signature_verifier.assert_valid(
                raw_body=raw_body,
                signature=event.signature,
            )
        else:
            event = parse_event(payload)

        await self._run_handlers(event)
        return event

    async def _run_handlers(self, event: EventModel) -> None:
        handlers = list(self._handlers.get(event.event, ())) + list(self._wildcard_handlers)
        if not handlers:
            _LOGGER.debug(
                "Received %s but no handlers are registered", event.event.value
            )
            return

        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:  # pragma: no cover - logged but propagated
                _LOGGER.exception(
                    "Webhook handler %r raised while processing %s",
                    getattr(handler, "__name__", handler),
                    event.event.value,
                )
                raise

    # ------------------------------------------------------------------
    # Inspection helpers
    # ------------------------------------------------------------------
    def listeners_for(self, event_type: WebhookEventType) -> List[EventHandler]:
        return list(self._handlers.get(event_type, ()))

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        counts = {key.value: len(value) for key, value in self._handlers.items()}
        return f"WebhookHandler(handlers={counts}, wildcards={len(self._wildcard_handlers)})"


# Re-export for convenience: callers often need only these symbols.
HandlerT: Type[Any] = WebhookHandler
"""Alias kept for typing convenience in user code."""
