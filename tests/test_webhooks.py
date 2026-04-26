"""Tests for the webhook parser and handler."""

from __future__ import annotations

import hashlib
import hmac as hmac_module

import pytest

from podpislon import (
    ClientDataRequestSubmittedEvent,
    DocumentOpenedEvent,
    DocumentSignedEvent,
    PodpislonUnknownEventError,
    PodpislonWebhookError,
    PodpislonWebhookSignatureError,
    WebhookEventType,
    WebhookHandler,
    WebhookSignatureVerifier,
    parse_event,
)


# ---------------------------------------------------------------------------
# parse_event
# ---------------------------------------------------------------------------
def test_parse_document_signed_from_form_bytes() -> None:
    body = b"EVENT=DOCUMENT_SIGNED&FILE_ID=1234&COMPANY_ID=12&SIGNATURE=1a2b3c4d5e6f"
    event = parse_event(body)
    assert isinstance(event, DocumentSignedEvent)
    assert event.event is WebhookEventType.DOCUMENT_SIGNED
    assert event.file_id == 1234
    assert event.company_id == 12
    assert event.signature == "1a2b3c4d5e6f"


def test_parse_document_opened_from_form_string() -> None:
    body = (
        "EVENT=DOCUMENT_OPENED&FILE_ID=5678&COMPANY_ID=21"
        "&SIGNATURE=9z8y7x6w5v4u&CONTACT=%2B79123456789"
    )
    event = parse_event(body)
    assert isinstance(event, DocumentOpenedEvent)
    assert event.file_id == 5678
    assert event.contact == "+79123456789"


def test_parse_client_data_request_from_mapping() -> None:
    payload = {
        "EVENT": "CLIENT_DATA_REQUEST_SUBMITTED",
        "COMPANY_ID": "12",
        "CLIENT_ID": "456",
        "CLIENT_NAME": "Иван",
        "CLIENT_LAST_NAME": "Иванов",
        "CLIENT_PHONE": "+79999999999",
        "SIGNATURE": "abc",
    }
    event = parse_event(payload)
    assert isinstance(event, ClientDataRequestSubmittedEvent)
    assert event.client_name == "Иван"
    assert event.client_last_name == "Иванов"


def test_parse_missing_event_raises() -> None:
    with pytest.raises(PodpislonWebhookError):
        parse_event(b"FILE_ID=1")


def test_parse_unknown_event_raises() -> None:
    with pytest.raises(PodpislonUnknownEventError):
        parse_event(b"EVENT=DOCUMENT_BURNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x")


# ---------------------------------------------------------------------------
# WebhookHandler
# ---------------------------------------------------------------------------
async def test_handler_dispatches_to_typed_listener() -> None:
    handler = WebhookHandler()
    seen: list[int] = []

    @handler.on(WebhookEventType.DOCUMENT_SIGNED)
    async def on_signed(event: DocumentSignedEvent) -> None:
        seen.append(event.file_id)

    body = b"EVENT=DOCUMENT_SIGNED&FILE_ID=1234&COMPANY_ID=12&SIGNATURE=x"
    event = await handler.dispatch(body)

    assert isinstance(event, DocumentSignedEvent)
    assert seen == [1234]


async def test_handler_supports_sync_callbacks() -> None:
    handler = WebhookHandler()
    calls: list[str] = []

    @handler.on(WebhookEventType.DOCUMENT_OPENED)
    def on_opened(event: DocumentOpenedEvent) -> None:
        calls.append(event.contact)

    body = b"EVENT=DOCUMENT_OPENED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x&CONTACT=%2B79991112233"
    await handler.dispatch(body)
    assert calls == ["+79991112233"]


async def test_handler_wildcard_listener() -> None:
    handler = WebhookHandler()
    seen: list[str] = []

    @handler.on_any
    async def audit(event):  # type: ignore[no-untyped-def]
        seen.append(event.event.value)

    await handler.dispatch(
        b"EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x"
    )
    await handler.dispatch(
        b"EVENT=DOCUMENT_OPENED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x&CONTACT=%2B79"
    )
    assert seen == ["DOCUMENT_SIGNED", "DOCUMENT_OPENED"]


async def test_handler_no_listeners_is_noop() -> None:
    handler = WebhookHandler()
    event = await handler.dispatch(
        b"EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x"
    )
    assert isinstance(event, DocumentSignedEvent)


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------
def test_signature_verifier_default_hmac() -> None:
    secret = "supersecret"
    body = b"EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=any"
    expected = hmac_module.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    verifier = WebhookSignatureVerifier(secret)
    assert verifier.verify(raw_body=body, signature=expected) is True
    assert verifier.verify(raw_body=body, signature="wrong") is False


def test_signature_verifier_custom_compute() -> None:
    secret = "secret"
    verifier = WebhookSignatureVerifier(
        secret,
        compute=lambda body, key: f"{key}:{body.decode('utf-8')}",
    )
    body = b"hello"
    assert verifier.verify(raw_body=body, signature="secret:hello") is True


async def test_handler_with_signature_failure() -> None:
    secret = "secret"
    handler = WebhookHandler(signature_verifier=WebhookSignatureVerifier(secret))
    body = b"EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=garbage"

    with pytest.raises(PodpislonWebhookSignatureError):
        await handler.dispatch(body)


async def test_handler_with_signature_success() -> None:
    secret = "secret"
    body_no_sig = "EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2"
    sig = hmac_module.new(
        secret.encode("utf-8"),
        body_no_sig.encode("utf-8") + b"&SIGNATURE=placeholder",
        hashlib.sha256,
    ).hexdigest()
    body = (body_no_sig + f"&SIGNATURE={sig}").encode("utf-8")

    handler = WebhookHandler(
        signature_verifier=WebhookSignatureVerifier(
            secret,
            # Use a permissive compute that returns whatever signature was provided.
            compute=lambda raw, key: sig,
        )
    )
    event = await handler.dispatch(body)
    assert isinstance(event, DocumentSignedEvent)


async def test_handler_runs_handlers_in_order() -> None:
    handler = WebhookHandler()
    order: list[str] = []

    @handler.on(WebhookEventType.DOCUMENT_SIGNED)
    async def first(event):  # type: ignore[no-untyped-def]
        order.append("first")

    @handler.on(WebhookEventType.DOCUMENT_SIGNED)
    async def second(event):  # type: ignore[no-untyped-def]
        order.append("second")

    @handler.on_any
    async def third(event):  # type: ignore[no-untyped-def]
        order.append("third")

    await handler.dispatch(
        b"EVENT=DOCUMENT_SIGNED&FILE_ID=1&COMPANY_ID=2&SIGNATURE=x"
    )
    assert order == ["first", "second", "third"]
