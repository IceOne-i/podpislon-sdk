"""FastAPI app that wraps the Podpislon SDK.

* ``POST /contracts/{contract_id}/sign`` — отправить документ на подпись.
* ``POST /webhooks/podpislon``           — приёмник вебхуков от сервиса.
* ``GET  /healthz``                       — простой health-check.

Запуск:

    pip install "podpislon-sdk[fastapi]" uvicorn[standard]
    PODPISLON_API_KEY=... uvicorn examples.fastapi_integration:app --reload
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from podpislon import (
    DocumentSignedEvent,
    DocumentOpenedEvent,
    PodpislonAPIError,
    PodpislonClient,
    PodpislonWebhookError,
    WebhookEventType,
    WebhookHandler,
)

# --------------------------------------------------------------------------
# Lifespan: один общий клиент SDK на процесс приложения.
# --------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    api_key = os.environ.get("PODPISLON_API_KEY")
    if not api_key:
        raise RuntimeError("PODPISLON_API_KEY is not set")

    app.state.podpislon = PodpislonClient(api_key=api_key)
    try:
        yield
    finally:
        await app.state.podpislon.aclose()


app = FastAPI(title="Podpislon SDK demo", lifespan=lifespan)


# --------------------------------------------------------------------------
# Webhook handlers
# --------------------------------------------------------------------------
webhooks = WebhookHandler()


@webhooks.on(WebhookEventType.DOCUMENT_SIGNED)
async def on_signed(event: DocumentSignedEvent) -> None:
    print(f"[webhook] DOCUMENT_SIGNED file_id={event.file_id} company_id={event.company_id}")


@webhooks.on(WebhookEventType.DOCUMENT_OPENED)
async def on_opened(event: DocumentOpenedEvent) -> None:
    print(f"[webhook] DOCUMENT_OPENED file_id={event.file_id} contact={event.contact}")


# --------------------------------------------------------------------------
# Routes
# --------------------------------------------------------------------------
class SignResponse(BaseModel):
    ids: list[int]
    links: list[str]


@app.post("/contracts/sign", response_model=SignResponse)
async def send_to_sign(
    request: Request,
    name: str,
    last_name: str,
    phone: str,
    contract: UploadFile,
) -> SignResponse:
    """Принимает PDF в multipart-форме и отправляет его на подпись."""

    client: PodpislonClient = request.app.state.podpislon
    pdf_bytes = await contract.read()

    try:
        result = await client.documents.add(
            name=name,
            last_name=last_name,
            phone=phone,
            files=[pdf_bytes],
            file_names=[contract.filename or "contract.pdf"],
            no_sms=True,
        )
    except PodpislonAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return SignResponse(ids=result.ids, links=result.links)


@app.post("/webhooks/podpislon")
async def webhook(request: Request) -> Response:
    body = await request.body()
    try:
        await webhooks.dispatch(body, raw_body=body)
    except PodpislonWebhookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(status_code=200)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
