"""Tests for :class:`DocumentsResource`."""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
import pytest

from podpislon import (
    Contact,
    DocumentStatus,
    Filter,
    PodpislonAPIError,
    PodpislonClient,
    PodpislonValidationError,
)


# ---------------------------------------------------------------------------
# list / iter_all
# ---------------------------------------------------------------------------
async def test_list_returns_documents_with_pagination(
    client: PodpislonClient, mock_api
) -> None:
    mock_api.post("/").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
                    "id": 101,
                    "name": "Акт №853",
                    "status": "30",
                    "status_text": "Подписан",
                    "package": "cb4b683",
                }
            ],
            headers={
                "x-pagination-current-page": "1",
                "x-pagination-page-count": "4",
                "x-pagination-per-page": "20",
                "x-pagination-total-count": "67",
            },
        )
    )

    page = await client.documents.list()

    assert len(page) == 1
    assert page.items[0].id == 101
    assert page.items[0].status == DocumentStatus.SIGNED
    assert page.items[0].status.description == "Подписан"
    assert page.pagination.current_page == 1
    assert page.pagination.page_count == 4
    assert page.pagination.total_count == 67
    assert page.has_next is True


async def test_list_with_filter_sends_request_body(
    client: PodpislonClient, mock_api
) -> None:
    route = mock_api.post("/").mock(
        return_value=httpx.Response(200, json=[], headers={})
    )

    await client.documents.list(
        page=2,
        filter=Filter(status=DocumentStatus.SIGNED, fio="Иван Иванов"),
        ids=[100, 315],
        expand="package",
    )

    request = route.calls.last.request
    assert request.url.params["page"] == "2"
    assert request.url.params["expand"] == "package"
    body = request.read().decode("utf-8")
    assert "Иван" in body
    assert '"status": "30"' in body or '"status":"30"' in body


async def test_iter_all_walks_every_page(client: PodpislonClient, mock_api) -> None:
    page_one = httpx.Response(
        200,
        json=[{"id": 1, "name": "first"}],
        headers={
            "x-pagination-current-page": "1",
            "x-pagination-page-count": "2",
            "x-pagination-per-page": "1",
            "x-pagination-total-count": "2",
        },
    )
    page_two = httpx.Response(
        200,
        json=[{"id": 2, "name": "second"}],
        headers={
            "x-pagination-current-page": "2",
            "x-pagination-page-count": "2",
            "x-pagination-per-page": "1",
            "x-pagination-total-count": "2",
        },
    )
    mock_api.post("/").mock(side_effect=[page_one, page_two])

    seen = [doc.id async for doc in client.documents.iter_all()]
    assert seen == [1, 2]


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------
async def test_add_requires_files(client: PodpislonClient) -> None:
    with pytest.raises(PodpislonValidationError):
        await client.documents.add(
            name="Иван", last_name="Иванов", phone="+79999999999", files=[]
        )


async def test_add_returns_single_id(client: PodpislonClient, mock_api) -> None:
    mock_api.put("/add-document").mock(
        return_value=httpx.Response(200, json={"status": True, "result": 101})
    )

    result = await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79999999999",
        files=[b"%PDF-1.4 fake"],
    )

    assert result.ids == [101]
    assert result.first_id == 101
    assert result.links == []


async def test_add_returns_array_of_ids(client: PodpislonClient, mock_api) -> None:
    mock_api.put("/add-document").mock(
        return_value=httpx.Response(200, json={"status": True, "result": [101, 102, 103]})
    )

    result = await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79999999999",
        files=[b"a", b"b", b"c"],
        file_names=["a.pdf", "b.pdf", "c.pdf"],
    )

    assert result.ids == [101, 102, 103]


async def test_add_with_no_sms_returns_links(client: PodpislonClient, mock_api) -> None:
    mock_api.put("/add-document").mock(
        return_value=httpx.Response(
            200,
            json={
                "status": True,
                "result": {
                    "ids": [101, 102],
                    "links": [
                        "https://podpislon.ru/sign/pack/aaa",
                        "https://podpislon.ru/sign/pack/bbb",
                    ],
                },
            },
        )
    )

    result = await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79999999999",
        files=[b"a", b"b"],
        file_names=["a.pdf", "b.pdf"],
        no_sms=True,
    )

    assert result.ids == [101, 102]
    assert result.first_link == "https://podpislon.ru/sign/pack/aaa"


async def test_add_json_mode_sends_base64(client: PodpislonClient, mock_api) -> None:
    route = mock_api.put("/add-document").mock(
        return_value=httpx.Response(200, json={"status": True, "result": 1})
    )

    await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79999999999",
        files=[b"%PDF-1.4 fake"],
        file_names=["doc.pdf"],
        use_multipart=False,
    )

    request_body = route.calls.last.request.read()
    assert b"file" in request_body
    assert b"fileName" in request_body
    assert b"doc.pdf" in request_body
    # Files come back base64 encoded inside the JSON body.
    encoded = base64.b64encode(b"%PDF-1.4 fake").decode("ascii").encode("ascii")
    assert encoded in request_body


async def test_add_with_extra_fields(client: PodpislonClient, mock_api) -> None:
    route = mock_api.put("/add-document").mock(
        return_value=httpx.Response(200, json={"status": True, "result": 1})
    )

    await client.documents.add(
        name="Иван",
        last_name="Иванов",
        phone="+79999999999",
        files=[b"x"],
        contacts=[
            Contact(
                name="Пётр",
                last_name="Петров",
                phone="+79111111111",
            )
        ],
        extra_fields={"custom_flag": "Z"},
    )

    body = route.calls.last.request.read()
    assert b"custom_flag" in body


async def test_add_status_false_raises(client: PodpislonClient, mock_api) -> None:
    mock_api.put("/add-document").mock(
        return_value=httpx.Response(
            200, json={"status": False, "mess": "Insufficient balance"}
        )
    )

    with pytest.raises(PodpislonAPIError):
        await client.documents.add(
            name="Иван",
            last_name="Иванов",
            phone="+79999999999",
            files=[b"x"],
        )


# ---------------------------------------------------------------------------
# get_file
# ---------------------------------------------------------------------------
async def test_get_file_returns_decoded_bytes(
    client: PodpislonClient, mock_api
) -> None:
    encoded = base64.b64encode(b"%PDF-1.4 hello").decode("ascii")
    mock_api.post("/get-file").mock(
        return_value=httpx.Response(200, json={"status": True, "result": encoded})
    )

    data = await client.documents.get_file(101)
    assert data == b"%PDF-1.4 hello"


async def test_get_file_can_skip_decoding(client: PodpislonClient, mock_api) -> None:
    encoded = base64.b64encode(b"x").decode("ascii")
    mock_api.post("/get-file").mock(
        return_value=httpx.Response(200, json={"status": True, "result": encoded})
    )

    data = await client.documents.get_file(101, decode=False)
    assert data == encoded


async def test_save_file_writes_to_disk(
    client: PodpislonClient, mock_api, tmp_path: Path
) -> None:
    encoded = base64.b64encode(b"%PDF-1.4").decode("ascii")
    mock_api.post("/get-file").mock(
        return_value=httpx.Response(200, json={"status": True, "result": encoded})
    )

    target = tmp_path / "out.pdf"
    written = await client.documents.save_file(101, target)
    assert written.exists()
    assert written.read_bytes() == b"%PDF-1.4"


async def test_get_file_validates_file_id(client: PodpislonClient) -> None:
    with pytest.raises(PodpislonValidationError):
        await client.documents.get_file("not-an-int")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# resend / delete
# ---------------------------------------------------------------------------
async def test_resend_sends_contact_in_body(
    client: PodpislonClient, mock_api
) -> None:
    route = mock_api.post("/resend/cb4b683").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )

    result = await client.documents.resend("cb4b683", contact="ODYxMjI=")
    assert result == {"ok": True}
    body = route.calls.last.request.read().decode("utf-8")
    assert "contact=ODYxMjI%3D" in body or "contact=ODYxMjI=" in body


async def test_resend_failure_raises(client: PodpislonClient, mock_api) -> None:
    mock_api.post("/resend/cb4b683").mock(
        return_value=httpx.Response(200, json={"ok": False, "mess": "limit reached"})
    )

    with pytest.raises(PodpislonAPIError):
        await client.documents.resend("cb4b683")


async def test_resend_validates_package_id(client: PodpislonClient) -> None:
    with pytest.raises(PodpislonValidationError):
        await client.documents.resend("")


async def test_delete_returns_payload(client: PodpislonClient, mock_api) -> None:
    mock_api.delete("/delete-document/101").mock(
        return_value=httpx.Response(200, json={"ok": True, "mess": "Документ удален"})
    )

    result = await client.documents.delete(101)
    assert result["ok"] is True
    assert result["mess"] == "Документ удален"


async def test_delete_failure_raises(client: PodpislonClient, mock_api) -> None:
    mock_api.delete("/delete-document/101").mock(
        return_value=httpx.Response(200, json={"ok": False, "mess": "no rights"})
    )

    with pytest.raises(PodpislonAPIError):
        await client.documents.delete(101)


async def test_delete_validates_file_id(client: PodpislonClient) -> None:
    with pytest.raises(PodpislonValidationError):
        await client.documents.delete("nope")  # type: ignore[arg-type]
