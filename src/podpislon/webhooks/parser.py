"""Parse raw webhook payloads into typed pydantic models."""

from __future__ import annotations

from typing import Mapping, Union
from urllib.parse import parse_qs

from podpislon.enums import WebhookEventType
from podpislon.exceptions import PodpislonUnknownEventError, PodpislonWebhookError
from podpislon.models.webhook import (
    ClientDataRequestSubmittedEvent,
    DocumentOpenedEvent,
    DocumentSignedEvent,
)

WebhookPayload = Union[bytes, str, Mapping[str, object]]
"""Anything we know how to turn into a webhook event."""

EVENT_TO_MODEL = {
    WebhookEventType.DOCUMENT_OPENED: DocumentOpenedEvent,
    WebhookEventType.DOCUMENT_SIGNED: DocumentSignedEvent,
    WebhookEventType.CLIENT_DATA_REQUEST_SUBMITTED: ClientDataRequestSubmittedEvent,
}


def parse_event(
    payload: WebhookPayload,
) -> Union[DocumentOpenedEvent, DocumentSignedEvent, ClientDataRequestSubmittedEvent]:
    """Convert an incoming webhook body into a typed event.

    Accepts the wire formats Podpislon actually uses:

    * ``bytes`` / ``str`` of an ``application/x-www-form-urlencoded`` body
      (the format documented in the OpenAPI spec);
    * a pre-parsed ``Mapping`` — handy for tests or when your framework
      already decoded the form for you.
    """

    fields = _normalise(payload)
    event_value = fields.get("EVENT") or fields.get("event")
    if not event_value:
        raise PodpislonWebhookError("Webhook payload is missing the EVENT field")

    try:
        event_type = WebhookEventType(event_value)
    except ValueError as exc:
        raise PodpislonUnknownEventError(
            f"Unknown webhook event type: {event_value!r}"
        ) from exc

    model_cls = EVENT_TO_MODEL[event_type]
    return model_cls.model_validate(fields)


def _normalise(payload: WebhookPayload) -> dict[str, str]:
    """Return a flat ``dict[str, str]`` regardless of the input shape."""

    if isinstance(payload, Mapping):
        return {str(k): _coerce_to_str(v) for k, v in payload.items()}

    if isinstance(payload, (bytes, bytearray)):
        text = payload.decode("utf-8", errors="replace")
    elif isinstance(payload, str):
        text = payload
    else:  # pragma: no cover - defensive
        raise TypeError(
            f"Unsupported webhook payload type: {type(payload).__name__}"
        )

    parsed = parse_qs(text, keep_blank_values=True, strict_parsing=False)
    # parse_qs returns list[str] per key — collapse to the first value because
    # Podpislon never uses repeated keys.
    return {key: values[0] if values else "" for key, values in parsed.items()}


def _coerce_to_str(value: object) -> str:
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)
