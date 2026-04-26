"""Models for incoming webhook events."""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from podpislon.enums import WebhookEventType
from podpislon.models.common import _PodpislonBase


class _BaseEvent(_PodpislonBase):
    """Common fields shared by every webhook payload."""

    event: WebhookEventType = Field(alias="EVENT")
    company_id: int = Field(alias="COMPANY_ID")
    signature: str = Field(alias="SIGNATURE")


class DocumentOpenedEvent(_BaseEvent):
    """Fires when a recipient opens the signing link."""

    event: Literal[WebhookEventType.DOCUMENT_OPENED] = Field(alias="EVENT")
    file_id: int = Field(alias="FILE_ID")
    contact: str = Field(alias="CONTACT", description="Phone number of the viewer.")


class DocumentSignedEvent(_BaseEvent):
    """Fires when every party has signed the document."""

    event: Literal[WebhookEventType.DOCUMENT_SIGNED] = Field(alias="EVENT")
    file_id: int = Field(alias="FILE_ID")


class ClientDataRequestSubmittedEvent(_BaseEvent):
    """Fires when a client fills out the personal-data request form."""

    event: Literal[WebhookEventType.CLIENT_DATA_REQUEST_SUBMITTED] = Field(alias="EVENT")
    client_id: int = Field(alias="CLIENT_ID")
    client_name: str = Field(alias="CLIENT_NAME")
    client_last_name: str = Field(alias="CLIENT_LAST_NAME")
    client_phone: str = Field(alias="CLIENT_PHONE")


WebhookEvent = Annotated[
    Union[DocumentOpenedEvent, DocumentSignedEvent, ClientDataRequestSubmittedEvent],
    Field(discriminator="event"),
]
"""Discriminated union of all known webhook events.

Use this as the type hint for handlers that accept any event:

.. code-block:: python

    async def handle(event: WebhookEvent) -> None:
        if isinstance(event, DocumentSignedEvent):
            ...
"""
