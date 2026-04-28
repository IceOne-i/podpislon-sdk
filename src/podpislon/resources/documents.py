"""Documents resource — list, add, fetch, resend, delete."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, AsyncIterator, List, Mapping, Optional, Sequence, Union

from podpislon._utils import (
    decode_base64_to_bytes,
    encode_file_to_base64,
    parse_int_header,
    to_form_data,
)
from podpislon.exceptions import PodpislonValidationError
from podpislon.models.common import PaginationMeta
from podpislon.models.contact import Contact
from podpislon.models.document import (
    AddDocumentResult,
    Document,
    Filter,
    PaginatedDocuments,
)
from podpislon.models.payment import Payment
from podpislon.resources._base import Resource

FileLike = Union[bytes, str, Path]
"""A PDF file accepted by :meth:`DocumentsResource.add`."""


class DocumentsResource(Resource):
    """Wraps every ``Document``-tagged endpoint of the API."""

    # ------------------------------------------------------------------
    # POST /  — list documents
    # ------------------------------------------------------------------
    async def list(
        self,
        *,
        page: int = 1,
        ids: Optional[Sequence[int]] = None,
        filter: Optional[Filter] = None,
        expand: Optional[str] = None,
    ) -> PaginatedDocuments:
        """List documents on a single page.

        ``filter`` accepts a :class:`~podpislon.models.document.Filter`
        object (use ``DocumentStatus`` enum members for the ``status``
        field). The result includes pagination metadata pulled from the
        ``x-pagination-*`` response headers.

        Pass ``expand="package"`` to include the package ID in each item —
        you'll need that for :meth:`resend`.
        """

        params: dict[str, Any] = {"page": page}
        if expand:
            params["expand"] = expand

        json_body: dict[str, Any] = {}
        if filter is not None:
            json_body["filter"] = filter.model_dump(exclude_none=True, mode="json")
        if ids:
            json_body["ids"] = list(ids)

        response = await self._transport.request(
            "POST",
            "/",
            params=params,
            json=json_body or None,
        )

        # The API returns either a bare array of documents or wraps it in
        # the standard envelope; tolerate both.
        body = response.json_body
        if isinstance(body, dict) and "result" in body:
            raw_items = body.get("result") or []
        elif isinstance(body, list):
            raw_items = body
        else:
            raw_items = []

        items = [Document.model_validate(item) for item in raw_items]
        pagination = PaginationMeta(
            current_page=parse_int_header(response.headers, "x-pagination-current-page"),
            page_count=parse_int_header(response.headers, "x-pagination-page-count"),
            per_page=parse_int_header(response.headers, "x-pagination-per-page"),
            total_count=parse_int_header(response.headers, "x-pagination-total-count"),
        )
        return PaginatedDocuments(items=items, pagination=pagination)

    async def iter_all(
        self,
        *,
        ids: Optional[Sequence[int]] = None,
        filter: Optional[Filter] = None,
        expand: Optional[str] = None,
        start_page: int = 1,
    ) -> AsyncIterator[Document]:
        """Iterate every document matching the filter, transparently paging."""

        page = start_page
        while True:
            result = await self.list(page=page, ids=ids, filter=filter, expand=expand)
            for doc in result.items:
                yield doc
            if not result.has_next:
                return
            page += 1

    # ------------------------------------------------------------------
    # PUT /add-document  — create + send a document
    # ------------------------------------------------------------------
    async def add(
        self,
        *,
        name: str,
        last_name: str,
        phone: str,
        files: Sequence[FileLike],
        agreement: str = "Y",
        second_name: Optional[str] = None,
        file_names: Optional[Sequence[str]] = None,
        contacts: Optional[Sequence[Contact]] = None,
        payment: Optional[Payment] = None,
        send_date: Optional[int] = None,
        stroke_doc: Optional[int] = None,
        no_sms: bool = False,
        redirect_url: Optional[str] = None,
        sign_by_time: Optional[int] = None,
        use_multipart: bool = True,
        extra_fields: Optional[Mapping[str, Any]] = None,
    ) -> AddDocumentResult:
        """Upload one or more PDFs and start the signing flow.

        Parameters
        ----------
        name, last_name, phone:
            Required signer details. ``second_name`` (patronymic) is optional.
        files:
            PDFs to send. Each item may be ``bytes``, a ``str`` path or a
            :class:`pathlib.Path`. At least one file is required by the API.
        file_names:
            Per-file display names. Required when sending raw bytes via JSON
            mode (``use_multipart=False``); inferred from path basenames in
            multipart mode.
        agreement:
            Personal-data processing consent, kept as ``"Y"`` per the API.
        contacts:
            Multiple signers, in addition to the primary one above.
        payment:
            Attach a payment to be collected at signing time.
        send_date:
            Unix timestamp — schedule the document for later delivery.
        stroke_doc:
            Pass ``1`` to enforce strict ordering between documents.
        no_sms:
            Set to ``True`` to receive direct signing links instead of
            sending an SMS to the signer. Conflicts with ``send_date`` —
            the API silently ignores ``no_sms`` in that case.
        redirect_url:
            Where to redirect the signer after signing (single-signer only).
        sign_by_time:
            Unix timestamp deadline by which the document must be signed.
        use_multipart:
            Default ``True`` — uploads files as binary ``multipart/form-data``
            (the most efficient transport). Set to ``False`` to send everything
            as JSON with base64-encoded files (useful when you can't open a
            multipart connection or you already have base64 payloads in hand).
        extra_fields:
            Escape hatch for fields not yet modelled by the SDK.
        """

        if not files:
            raise PodpislonValidationError("At least one PDF file must be provided")

        base_payload: dict[str, Any] = {
            "name": name,
            "last_name": last_name,
            "phone": phone,
            "agreement": agreement,
        }
        if second_name is not None:
            base_payload["second_name"] = second_name
        if contacts:
            base_payload["contacts"] = [c.model_dump(exclude_none=True) for c in contacts]
        if payment is not None:
            base_payload["payment"] = payment.model_dump(exclude_none=True)
        if send_date is not None:
            base_payload["send_date"] = send_date
        if stroke_doc is not None:
            base_payload["stroke_doc"] = stroke_doc
        if no_sms:
            base_payload["no_sms"] = "Y"
        if redirect_url is not None:
            base_payload["redirect_url"] = redirect_url
        if sign_by_time is not None:
            base_payload["sign_by_time"] = sign_by_time
        if extra_fields:
            base_payload.update(extra_fields)

        # Despite the HTTP method, /add-document is NOT idempotent: every
        # successful call creates a brand-new draft on Podpislon's side.
        # Mark it explicitly so the retry policy refuses to replay it on
        # 5xx or read-side errors — duplicating a draft would silently
        # double-bill the customer's signing balance.
        if use_multipart:
            response = await self._transport.request(
                "PUT",
                "/add-document",
                data=to_form_data(base_payload),
                files=self._build_multipart_files(files, file_names),
                idempotent=False,
            )
        else:
            base_payload["file"] = [encode_file_to_base64(f) for f in files]
            base_payload["fileName"] = list(self._resolve_file_names(files, file_names))
            response = await self._transport.request(
                "PUT",
                "/add-document",
                json=base_payload,
                idempotent=False,
            )

        result = self._unwrap_status_envelope(response.json_body, expected_key="result")
        return AddDocumentResult.from_api(result)

    # ------------------------------------------------------------------
    # POST /get-file  — retrieve a signed document
    # ------------------------------------------------------------------
    async def get_file(self, file_id: int, *, decode: bool = True) -> bytes | str:
        """Return the PDF for the given document.

        ``decode=True`` (the default) returns raw bytes; pass ``False`` to
        get the original base64 string instead.
        """

        if not isinstance(file_id, int):
            raise PodpislonValidationError("file_id must be an integer")

        response = await self._transport.request(
            "POST",
            "/get-file",
            data={"id": file_id},
        )
        result = self._unwrap_status_envelope(response.json_body, expected_key="result")
        if not isinstance(result, str):
            raise PodpislonValidationError(
                f"Unexpected response shape for /get-file: {type(result).__name__}"
            )
        if decode:
            return decode_base64_to_bytes(result)
        return result

    async def save_file(self, file_id: int, destination: str | Path) -> Path:
        """Convenience helper: download a document and write it to disk."""

        data = await self.get_file(file_id, decode=True)
        assert isinstance(data, bytes)
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    # ------------------------------------------------------------------
    # POST /resend/{package_id}  — resend signing link
    # ------------------------------------------------------------------
    async def resend(self, package_id: str, *, contact: Optional[str] = None) -> dict[str, Any]:
        """Resend the signing link to a specific contact.

        ``contact`` is the signer's ``sid`` (server-assigned ID) returned by
        the listing endpoint. The API caps resends at 5 per package.
        """

        if not package_id:
            raise PodpislonValidationError("package_id must be a non-empty string")

        data: dict[str, Any] = {}
        if contact:
            data["contact"] = contact

        # /resend triggers an SMS to the signer; replaying on a 5xx could
        # send the same SMS twice and bring the per-package resend counter
        # closer to its limit (5).
        response = await self._transport.request(
            "POST",
            f"/resend/{package_id}",
            data=data or None,
            idempotent=False,
        )
        body = response.json_body or {}
        if body.get("ok") is False:
            from podpislon.exceptions import PodpislonAPIError

            raise PodpislonAPIError(
                body.get("mess") or "Resend failed",
                response_body=body,
            )
        return body

    # ------------------------------------------------------------------
    # DELETE /delete-document/{file_id}
    # ------------------------------------------------------------------
    async def delete(self, file_id: int) -> dict[str, Any]:
        """Delete a document owned by the company."""

        if not isinstance(file_id, int):
            raise PodpislonValidationError("file_id must be an integer")

        response = await self._transport.request(
            "DELETE",
            f"/delete-document/{file_id}",
        )
        body = response.json_body or {}
        if body.get("ok") is False:
            from podpislon.exceptions import PodpislonAPIError

            raise PodpislonAPIError(
                body.get("mess") or "Delete failed",
                response_body=body,
            )
        return body

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _build_multipart_files(
        files: Sequence[FileLike],
        file_names: Optional[Sequence[str]] = None,
    ) -> list[tuple[str, tuple[str, bytes, str]]]:
        """Materialise ``files`` into the tuple form expected by httpx.

        The Podpislon API only accepts PDF (per the OpenAPI spec); we still
        derive the per-part Content-Type from the filename via
        ``mimetypes.guess_type`` so a non-PDF upload is labelled honestly
        instead of being mis-tagged ``application/pdf``. That way the
        upstream's content-type validation can reject it instead of
        silently storing an empty document.
        """

        names = list(DocumentsResource._resolve_file_names(files, file_names))
        result: list[tuple[str, tuple[str, bytes, str]]] = []
        for index, source in enumerate(files):
            data = _read_file_bytes(source)
            field_name = "file[]"  # Yii-flavoured array field name
            guessed, _ = mimetypes.guess_type(names[index])
            content_type = guessed or "application/pdf"
            result.append((field_name, (names[index], data, content_type)))
        return result

    @staticmethod
    def _resolve_file_names(
        files: Sequence[FileLike],
        file_names: Optional[Sequence[str]],
    ) -> Sequence[str]:
        if file_names is not None:
            if len(file_names) != len(files):
                raise PodpislonValidationError(
                    "file_names must have the same length as files"
                )
            return list(file_names)

        resolved: list[str] = []
        for index, source in enumerate(files):
            if isinstance(source, (str, Path)):
                resolved.append(Path(source).name)
            else:
                resolved.append(f"document_{index + 1}.pdf")
        return resolved


def _read_file_bytes(source: FileLike) -> bytes:
    if isinstance(source, (bytes, bytearray)):
        return bytes(source)
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")
        return path.read_bytes()
    raise TypeError(
        f"Unsupported file source: {type(source).__name__}; "
        "expected bytes, str path or pathlib.Path"
    )
