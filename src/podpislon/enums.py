"""Enumerations used by the Podpislon API.

All values are kept as ``str`` to round-trip cleanly through the wire format
(the API uses string status codes such as ``"30"``).
"""

from __future__ import annotations

from enum import Enum


class DocumentStatus(str, Enum):
    """Lifecycle states of a document.

    The numeric strings come straight from the API. Descriptions reproduced
    from the OpenAPI specification.
    """

    CREATED = "10"           # Создан
    SENT = "15"              # Отправлен
    OPENED = "20"            # Просмотрен
    SIGNED = "30"            # Подписан
    CANCEL_REQUESTED = "35"  # Запрошено аннулирование
    CANCELLED = "40"         # Аннулирован

    @property
    def description(self) -> str:
        return _STATUS_DESCRIPTIONS[self]


_STATUS_DESCRIPTIONS: dict["DocumentStatus", str] = {
    DocumentStatus.CREATED: "Создан",
    DocumentStatus.SENT: "Отправлен",
    DocumentStatus.OPENED: "Просмотрен",
    DocumentStatus.SIGNED: "Подписан",
    DocumentStatus.CANCEL_REQUESTED: "Запрошено аннулирование",
    DocumentStatus.CANCELLED: "Аннулирован",
}


class WebhookEventType(str, Enum):
    """Event types delivered to your webhook endpoint."""

    DOCUMENT_OPENED = "DOCUMENT_OPENED"
    DOCUMENT_SIGNED = "DOCUMENT_SIGNED"
    CLIENT_DATA_REQUEST_SUBMITTED = "CLIENT_DATA_REQUEST_SUBMITTED"
