"""Tests for low-level utilities."""

from __future__ import annotations

import asyncio
import time

import pytest

from podpislon._utils import (
    AsyncRateLimiter,
    chunked,
    decode_base64_to_bytes,
    encode_file_to_base64,
    parse_int_header,
    to_form_data,
)


def test_to_form_data_flattens_nested_dict() -> None:
    result = to_form_data(
        {
            "name": "Иван",
            "filter": {"status": "30", "dates": {">=": "1", "<=": "2"}},
        }
    )
    assert result == {
        "name": "Иван",
        "filter[status]": "30",
        "filter[dates][>=]": "1",
        "filter[dates][<=]": "2",
    }


def test_to_form_data_flattens_arrays() -> None:
    result = to_form_data({"ids": [1, 2, 3]})
    assert result == {"ids[0]": 1, "ids[1]": 2, "ids[2]": 3}


def test_to_form_data_drops_none() -> None:
    assert to_form_data({"a": None, "b": 1}) == {"b": 1}


def test_to_form_data_bool_to_y() -> None:
    assert to_form_data({"agreement": True})["agreement"] == "Y"
    assert to_form_data({"agreement": False})["agreement"] == ""


def test_encode_decode_roundtrip(tmp_path) -> None:
    path = tmp_path / "x.pdf"
    path.write_bytes(b"%PDF-1.4")
    encoded = encode_file_to_base64(path)
    assert decode_base64_to_bytes(encoded) == b"%PDF-1.4"


def test_encode_from_bytes() -> None:
    encoded = encode_file_to_base64(b"hello")
    assert decode_base64_to_bytes(encoded) == b"hello"


def test_encode_missing_file(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        encode_file_to_base64(tmp_path / "missing.pdf")


def test_chunked() -> None:
    assert list(chunked([1, 2, 3, 4, 5], 2)) == [[1, 2], [3, 4], [5]]
    assert list(chunked([], 3)) == []
    with pytest.raises(ValueError):
        list(chunked([1, 2], 0))


def test_parse_int_header() -> None:
    assert parse_int_header({"x-pagination-current-page": "3"}, "x-pagination-current-page") == 3
    assert parse_int_header({}, "missing") is None
    assert parse_int_header({"X-Pagination-Total-Count": "5"}, "x-pagination-total-count") == 5
    assert parse_int_header({"x": "garbage"}, "x") is None


async def test_rate_limiter_throttles() -> None:
    limiter = AsyncRateLimiter(rate=2, per=0.4)

    timestamps: list[float] = []

    async def call() -> None:
        async with limiter.slot():
            timestamps.append(time.monotonic())

    start = time.monotonic()
    await asyncio.gather(*(call() for _ in range(4)))
    duration = time.monotonic() - start

    # Two slots fit within the first window, the next two must wait at
    # least one full window — so total time is ≥ ~0.4s.
    assert duration >= 0.35
    assert len(timestamps) == 4


def test_rate_limiter_validates_inputs() -> None:
    with pytest.raises(ValueError):
        AsyncRateLimiter(rate=0)
    with pytest.raises(ValueError):
        AsyncRateLimiter(rate=4, per=0)
